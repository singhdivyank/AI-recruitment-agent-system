"""
Sourcing Agent
Executes parallel fan-out to LinkedIn, Naukri, and ATS.
Handles pagination, empty results, and transient failures independently
so a single source failure does not block the pipeline.
"""
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List, Optional

import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.schemas import (
    CandidateProfile,
    CandidateStatus, 
    EducationEntry, 
    EmploymentEntry,
    JDCreate, 
    JDParsed, 
    SourcePlatform, 
    SourceProfile, 
    WorkflowState,
)
from db.models import JDModel
from observability.telemetry import observe_agent, record_tool_call
from utils.prometheus_metrics import CANDIDATES_SOURCED, SOURCING_DURATION
from tools.mcp_client import (
    MCPCallError,
    ats_search_profiles,
    ats_update_status,
    linkedin_search_profiles,
    naukri_search_profiles
)

logger = structlog.get_logger()

def _dict_to_profile(d: Dict[str, Any]) -> Optional[CandidateProfile]:
    """Convert a raw dict returned by an MCP server into a CandidateProfile."""
    if not d or "error" in d:
        return None
    try:
        education = [
            EducationEntry(**e) if isinstance(e, dict) else e
            for e in (d.get("education", []))
        ]
        employment = [
            EmploymentEntry(**e) if isinstance(e, dict) else e
            for e in (d.get("employment_history", []))
        ]
        src_name = (d.get("source", "linkedin")).capitalize()
        try:
            src_platform = SourcePlatform(src_name)
        except ValueError:
            src_platform = SourcePlatform.LINKEDIN

        source_profiles = d.get("source_profiles", [])
        parsed_source_profiles = []
        for sp in source_profiles:
            if isinstance(sp, dict):
                try:
                    parsed_source_profiles.append(SourceProfile(
                        source=SourcePlatform(sp.get("source", src_name)),
                        url=sp.get("url"),
                        raw_id=sp.get("raw_id"),
                    ))
                except Exception:
                    pass

        return CandidateProfile(
            candidate_id=d["candidate_id"],
            name=d.get("name", ""),
            email=d.get("email"),
            phone=d.get("phone"),
            location=d.get("location"),
            skills=d.get("skills", []),
            experience_years=float(d.get("experience_years", 0)),
            education=education,
            employment_history=employment,
            summary=d.get("summary"),
            linkedin_url=d.get("linkedin_url"),
            source_profiles=parsed_source_profiles,
            status=CandidateStatus.SOURCED,
        )
    except Exception as exc:
        logger.debug("mcp_profile_parse_error", error=str(exc))
        return None


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

    async def _fetch_pages(
        self,
        search_fn,
        source_label: str,
        jd_title: str,
        skills: List[str],
        location: Optional[str],
        min_years: int,
        max_pages: int = 3,
    ) -> List[CandidateProfile]:
        """
        Paginate through a single MCP source.
        Stops on empty page or on transient failure (does not raise).
        """
        all_profiles: List[CandidateProfile] = []
        for page in range(max_pages):
            start = time.monotonic()
            try:
                result = await search_fn(
                    jd_title=jd_title,
                    skills=skills,
                    location=location,
                    min_years=min_years,
                    page=page,
                    page_size=50,
                )
                record_tool_call(f"mcp_{source_label}_search", time.monotonic() - start)

                raw_profiles = result.get("profiles", [])
                if not raw_profiles:
                    break  # empty page = exhausted

                converted = [_dict_to_profile(p) for p in raw_profiles]
                valid = [p for p in converted if p is not None]
                all_profiles.extend(valid)
                CANDIDATES_SOURCED.labels(source=source_label).inc(len(valid))

            except MCPCallError as exc:
                record_tool_call(f"mcp_{source_label}_search", time.monotonic() - start, success=False)
                logger.warning("mcp_source_page_error", source=source_label, page=page, error=str(exc))
                break  # transient failure — use what we have
            except Exception as exc:
                record_tool_call(f"mcp_{source_label}_search", time.monotonic() - start, success=False)
                logger.error("mcp_source_unexpected_error", source=source_label, page=page, error=str(exc))
                break

        return all_profiles

    @observe_agent("sourcing_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd_id = state.jd_id
        jd = state.jd_raw
        jd_parsed = state.jd_parsed
        log = logger.bind(agent="sourcing", jd_id=jd_id)
        log.info("start")

        title = jd_parsed.title if jd_parsed else jd.title
        skills = jd_parsed.must_have_skills if jd_parsed else jd.must_have_skills
        location = jd.location
        min_years = jd.years_experience.min

        # Update JD status
        stmt = select(JDModel).where(JDModel.jd_id == jd_id)
        result = await self.db.execute(stmt)
        jd_model = result.scalar_one_or_none()
        if jd_model:
            jd_model.status = "SOURCING"

        start = time.monotonic()

        # ── Fan-Out: call all three MCP servers in parallel ──────
        linkedin_task = asyncio.create_task(
            self._fetch_pages(linkedin_search_profiles, "linkedin", title, skills, location, min_years)
        )
        naukri_task = asyncio.create_task(
            self._fetch_pages(naukri_search_profiles, "naukri", title, skills, location, min_years)
        )
        ats_task = asyncio.create_task(
            self._fetch_pages(ats_search_profiles, "ats", title, skills, location, min_years)
        )

        gathered = await asyncio.gather(
            linkedin_task, naukri_task, ats_task,
            return_exceptions=True,
        )

        # ── Fan-In: merge all results ────────────────────────────
        for name, result in zip(self.source_names, gathered):
            if isinstance(result, BaseException):
                log.error("mcp_source_failed", source=name, error=str(result))
                continue
            
            log.info("mcp_source_success", source=name, count=len(result))
            self.all_profiles.extend(result)

        # ── Write-back: mark sourced candidates in ATS ───────────
        # Only do this for a small sample to avoid hammering the ATS MCP
        ats_candidates = [p for p in self.all_profiles if any(
            sp.source == SourcePlatform.ATS for sp in p.source_profiles
        )]
        if ats_candidates:
            update_tasks = [
                ats_update_status(p.candidate_id, "SCREENING", "sourcing-agent")
                for p in ats_candidates[:10]  # limit write-backs
            ]
            update_results = await asyncio.gather(*update_tasks, return_exceptions=True)
            successful_updates = sum(1 for r in update_results if not isinstance(r, Exception))
            log.info("ats_status_updated", count=successful_updates)

        elapsed = time.monotonic() - start
        SOURCING_DURATION.observe(elapsed)
        log.info(
            "sourcing_complete",
            total=len(self.all_profiles),
            elapsed_s=round(elapsed, 2),
            transport="MCP/SSE",
        )

        state.raw_profiles = [p.model_dump() for p in self.all_profiles]
        state.step = "sourced"
        return state
