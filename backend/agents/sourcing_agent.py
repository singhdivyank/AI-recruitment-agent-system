"""
Sourcing Agent
Executes parallel fan-out to LinkedIn, Naukri, and ATS.
Handles pagination, empty results, and transient failures independently
so a single source failure does not block the pipeline.
"""
from __future__ import annotations
import asyncio
import time
from typing import List, Optional

import structlog

from backend.core.schemas import CandidateProfile, WorkflowState, JDCreate, JDParsed
from backend.db.models import JDModel
from backend.observability.telemetry import observe_agent
from backend.tools.sourcing_tools import search_ats, search_linkedin, search_naukri
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = structlog.get_logger()


class SourcingAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.all_profiles: List[CandidateProfile] = []
        self.source_names: List[str] = ["linkedin", "naukri", "ats"]
    
    def _get_details(self, jd: JDCreate, jd_parsed: Optional[JDParsed]):
        self.title = jd_parsed.title if jd_parsed else jd.title
        self.skills = jd_parsed.must_have_skills if jd_parsed else jd.must_have_skills
        self.location = jd.location
        self.min_years = jd.years_experience.min

    async def _search_with_pagination(
        self,
        search_fn,
        jd_title: str,
        must_have_skills: List[str],
        location: str,
        min_years: int,
        max_pages: int = 3,
    ) -> List[CandidateProfile]:
        """Fetch multiple pages from a source, stop when empty."""
        all_results = []
        for page in range(max_pages):
            try:
                results = await search_fn(
                    jd_title=jd_title,
                    must_have_skills=must_have_skills,
                    location=location,
                    min_years=min_years,
                    page=page,
                )
                if not results:
                    break  # empty page = end of results
                all_results.extend(results)
            except Exception as exc:
                logger.warning(
                    "source_page_error",
                    fn=search_fn.__name__,
                    page=page,
                    error=str(exc),
                )
                break  # transient failure — don't block, use what we have
        return all_results

    @observe_agent("sourcing_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd_id = state.jd_id
        jd = state.jd_raw
        jd_parsed = state.jd_parsed
        log = logger.bind(agent="sourcing", jd_id=jd_id)
        log.info("start")

        self._get_details(jd, jd_parsed)

        # Update JD status to SOURCING
        stmt = select(JDModel).where(JDModel.jd_id == jd_id)
        result = await self.db.execute(stmt)
        jd_model = result.scalar_one_or_none()
        if jd_model:
            jd_model.status = "SOURCING"

        start = time.monotonic()

        # ── Fan-Out: all three sources in parallel ──────────────
        linkedin_task = asyncio.create_task(
            self._search_with_pagination(
                search_linkedin, 
                self.title, 
                self.skills, 
                self.location, 
                self.min_years
            )
        )
        naukri_task = asyncio.create_task(
            self._search_with_pagination(
                search_naukri, 
                self.title, 
                self.skills, 
                self.location, 
                self.min_years
            )
        )
        ats_task = asyncio.create_task(
            self._search_with_pagination(
                search_ats, 
                self.title, 
                self.skills, 
                self.location, 
                self.min_years
            )
        )

        # Gather results — return_exceptions=True so one failure doesn't kill others
        results = await asyncio.gather(
            linkedin_task, naukri_task, ats_task,
            return_exceptions=True,
        )
        
        for name, result in zip(self.source_names, results):
            if not isinstance(result, Exception):
                log.info("source_success", source=name, count=len(result))
                self.all_profiles.extend(result)
            else:
                log.error("source_failed", source=name, error=str(result))

        elapsed = time.monotonic() - start
        log.info("sourcing_complete", total=len(self.all_profiles), elapsed_s=round(elapsed, 2))

        # ── Fan-In: aggregate into raw_profiles ────────────────
        state.raw_profiles = [p.model_dump() for p in self.all_profiles]
        state.step = "sourced"
        return state
