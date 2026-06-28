"""
Closure Agent — closes JD, records audit trail
"""
from __future__ import annotations

from typing import List

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_client import LLMClient
from core.schemas import JDCloseRequest
from db.models import AuditModel, CandidateModel, JDModel
from observability.telemetry import observe_agent
from utils.helpers import create_justification_prompt
from utils.prompts import CLOSURE_SYSTEM_PROMPT
from utils.prometheus_metrics import JDS_CLOSED

logger = structlog.get_logger()


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
        response = await self.llm.call_with_retry(
            system_prompt=CLOSURE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            agent_name="closure_agent",
            use_flash=True,
        )
        content = response.content
        
        if isinstance(content, str):
            return content
        if isinstance(content, List):
            if isinstance(content[0], str):
                return content[0]
        
        return str(content)
