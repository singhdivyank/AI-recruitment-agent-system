"""
Compliance Agent
Detects discriminatory content in JDs.
Protected attributes: gender, age, religion, ethnicity, marital status, nationality.
Uses both rule-based (fast) and LLM-based (thorough) detection.
"""
from __future__ import annotations
import re
from typing import List

import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm_client import LLMClient
from backend.core.schemas import WorkflowState
from backend.db.models import AuditModel, JDModel
from backend.observability.telemetry import observe_agent
from backend.utils.consts import DISALLOWED_PATTERNS
from backend.utils.prompts import COMPLIANCE_SYSTEM_PROMPT
from backend.utils.prometheus_metrics import JDS_REJECTED

logger = structlog.get_logger()


class ComplianceAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession):
        self.llm = llm
        self.db = db

    def _rule_based_check(self, text: str) -> List[str]:
        """Fast regex pre-scan."""
        text_lower = text.lower()
        flags = []
        for pattern in DISALLOWED_PATTERNS:
            if re.search(pattern, text_lower):
                flags.append(f"Pattern match: '{pattern}'")
        return flags

    @observe_agent("compliance_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd = state.jd_raw
        jd_id = state.jd_id
        log = logger.bind(agent="compliance", jd_id=jd_id)
        log.info("start")

        full_text = f"{jd.title}\n{jd.description}\n{' '.join(jd.must_have_skills)}"

        # Fast rule-based check first
        rule_flags = self._rule_based_check(full_text)

        # LLM deep scan (use flash — cheaper, sufficient for classification)
        try:
            result = await self.llm.call_json(
                system_prompt=COMPLIANCE_SYSTEM_PROMPT,
                user_prompt=f"Job Description:\n{full_text}",
                agent_name="compliance_agent",
                jd_id=jd_id,
                use_flash=True,   # Flash is sufficient + cheaper for binary classification
            )
            passed = result.get("passed", True)
            llm_flags = result.get("flags", [])
        except Exception as exc:
            log.warning("llm_compliance_failed_falling_back_to_rules", error=str(exc))
            passed = len(rule_flags) == 0
            llm_flags = []

        all_flags = list(set(rule_flags + llm_flags))

        # If any flags found, fail compliance
        if all_flags:
            passed = False

        # Update DB
        from sqlalchemy import select
        stmt = select(JDModel).where(JDModel.jd_id == jd_id)
        result_db = await self.db.execute(stmt)
        jd_model = result_db.scalar_one_or_none()
        if jd_model:
            jd_model.compliance_passed = passed
            jd_model.compliance_flags = all_flags
            if not passed:
                jd_model.status = "REJECTED"
                JDS_REJECTED.inc()
                self.db.add(AuditModel(
                    jd_id=jd_id,
                    recruiter_id="system",
                    action="JD_REJECTED_COMPLIANCE",
                    reason="; ".join(all_flags),
                ))

        state.compliance_passed = passed
        state.compliance_flags = all_flags
        state.step = "compliance_checked"

        if passed:
            log.info("compliance_passed")
        else:
            log.warning("compliance_failed", flags=all_flags)

        return state
