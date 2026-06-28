"""
Normalization Agent: raw profiles → unified CandidateProfile schema
"""
from __future__ import annotations
from typing import Any, Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import (
    CandidateProfile, CandidateStatus, WorkflowState
)
from observability.telemetry import observe_agent

logger = structlog.get_logger()


class NormalizationAgent:
    """Ensures all profiles conform to the unified CandidateProfile schema."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize(self, raw: Dict[str, Any]) -> Optional[CandidateProfile]:
        """
        Profiles sourced from the HF dataset are already CandidateProfile dicts.
        This layer validates, cleans, and enriches them.
        """
        try:
            profile = CandidateProfile(**raw)

            # Clean skills
            profile.skills = list(dict.fromkeys(
                [s.strip() for s in profile.skills if s and len(s.strip()) > 1]
            ))[:30]

            # Normalize location
            if profile.location:
                profile.location = profile.location.strip().title()

            # Set status
            profile.status = CandidateStatus.NORMALIZED

            return profile
        except Exception as exc:
            logger.debug("normalization_skip", error=str(exc))
            return None

    @observe_agent("normalization_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        log = logger.bind(agent="normalization", jd_id=state.jd_id)
        log.info("start", raw_count=len(state.raw_profiles))

        normalized = []
        for raw in state.raw_profiles:
            profile = self._normalize(raw)
            if profile:
                normalized.append(profile)

        log.info("complete", normalized=len(normalized), dropped=len(state.raw_profiles) - len(normalized))
        state.normalized_profiles = normalized
        state.step = "normalized"
        return state

