"""
Outreach Agent — drafts recruiter outreach messages for shortlisted candidates
"""
from __future__ import annotations
import asyncio
from typing import Dict, Optional

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_client import LLMClient
from core.schemas import (
    CandidateProfile, JDParsed,
    RankedCandidate, WorkflowState
)
from db.models import CandidateModel
from observability.telemetry import observe_agent
from utils.helpers import create_outreach_user_prompt
from utils.prompts import OUTREACH_SYSTEM_PROMPT

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
