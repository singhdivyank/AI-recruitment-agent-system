"""
Outreach Agent — drafts recruiter outreach messages for shortlisted candidates
Closure Agent — closes JD, records audit trail
"""
from __future__ import annotations
import asyncio
from typing import Dict, Optional

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm_client import LLMClient
from backend.core.schemas import (
    CandidateProfile, JDCloseRequest, JDParsed,
    RankedCandidate, WorkflowState
)
from backend.db.models import AuditModel, CandidateModel, JDModel
from backend.observability.telemetry import observe_agent
from backend.utils.helpers import create_outreach_user_prompt, create_justification_prompt
from backend.utils.prompts import OUTREACH_SYSTEM_PROMPT, CLOSURE_SYSTEM_PROMPT
from backend.utils.prometheus_metrics import JDS_CLOSED

logger = structlog.get_logger()


class OutreachAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession):
        self.llm = llm
        self.db = db

    async def _draft_outreach(
        self,
        candidate: CandidateProfile,
        jd_parsed: Optional[JDParsed],
        jd_id: str,
    ) -> Dict[str, str]:
        
        try:
            user_prompt = create_outreach_user_prompt(jd_parsed, candidate)
            result = await self.llm.call_json(
                system_prompt=OUTREACH_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name="outreach_agent",
                jd_id=jd_id,
                use_flash=True,   # Flash sufficient for outreach drafting
            )
            return result
        except Exception as exc:
            logger.error("outreach_draft_failed", candidate=candidate.name, error=str(exc))
            title = jd_parsed.title if jd_parsed else "NO TITLE EXTRACTED"
            return {
                "subject": f"Exciting {title} Opportunity",
                "body": f"Hi {candidate.name.split()[0]},\n\nYour experience aligns well with our {title} role. We'd love to connect!\n\nBest regards",
            }

    @observe_agent("outreach_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd_id = state.jd_id
        jd_parsed: Optional[JDParsed] = state.jd_parsed
        shortlist = state.shortlist
        log = logger.bind(agent="outreach", jd_id=jd_id)

        if not shortlist:
            log.warning("no_shortlist")
            return state

        log.info("start", candidates=len(shortlist.shortlist))

        # ── Fan-Out: draft outreach for all shortlisted candidates in parallel ──
        sem = asyncio.Semaphore(3)

        async def draft_with_sem(rc: RankedCandidate):
            async with sem:
                draft = await self._draft_outreach(rc.candidate, jd_parsed, jd_id)
                rc.outreach_draft = f"Subject: {draft['subject']}\n\n{draft['body']}"
                # Persist to DB
                await self.db.execute(
                    update(CandidateModel)
                    .where(CandidateModel.candidate_id == rc.candidate.candidate_id)
                    .values(outreach_draft=rc.outreach_draft)
                )
                return rc.candidate.candidate_id, rc.outreach_draft

        results = await asyncio.gather(
            *[draft_with_sem(rc) for rc in shortlist.shortlist],
            return_exceptions=True,
        )

        drafts = {}
        for result in results:
            if not isinstance(result, Exception):
                cid, draft = result
                drafts[cid] = draft

        state.outreach_drafts = drafts
        state.step = "outreach_drafted"
        log.info("outreach_complete", drafted=len(drafts))
        return state


class ClosureAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession):
        self.llm = llm
        self.db = db

    @observe_agent("closure_agent")
    async def close(self, close_req: JDCloseRequest, shortlist_snapshot: dict) -> AuditModel:
        log = logger.bind(agent="closure", jd_id=close_req.jd_id)
        log.info("closing_jd", candidate=close_req.selected_candidate_id)

        # Build justification
        try:
            justification = await self._build_justification(close_req, shortlist_snapshot)
        except Exception:
            justification = f"Candidate {close_req.selected_candidate_id} selected by recruiter."

        # Update JD status
        await self.db.execute(
            update(JDModel)
            .where(JDModel.jd_id == close_req.jd_id)
            .values(status="CLOSED")
        )

        # Update selected candidate status
        await self.db.execute(
            update(CandidateModel)
            .where(CandidateModel.candidate_id == close_req.selected_candidate_id)
            .values(status="SELECTED")
        )

        # Write audit record
        audit = AuditModel(
            jd_id=close_req.jd_id,
            selected_candidate_id=close_req.selected_candidate_id,
            candidate_name=shortlist_snapshot.get("name", "Unknown"),
            recruiter_id=close_req.recruiter_id,
            action="JD_CLOSED",
            reason=justification,
            ranking_snapshot=shortlist_snapshot,
        )
        self.db.add(audit)
        await self.db.flush()

        JDS_CLOSED.inc()
        log.info("jd_closed", recruiter=close_req.recruiter_id)
        return audit

    async def _build_justification(self, req: JDCloseRequest, snapshot: dict) -> str:
        user_prompt = create_justification_prompt(snapshot=snapshot, req=req)
        return await self.llm.call_with_retry(
            system_prompt=CLOSURE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            agent_name="closure_agent",
            use_flash=True,
        )
