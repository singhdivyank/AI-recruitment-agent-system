"""
Formal Tool Registry — matches the spec's TOOLS dict exactly.

TOOLS = {
    "search_linkedin":  linkedin_search_tool,
    "search_naukri":    naukri_search_tool,
    "search_ats":       ats_search_tool,
    "fetch_profile":    fetch_profile_tool,
    "score_candidate":  score_candidate_tool,
    "draft_outreach":   outreach_tool,
    "update_jd_state":  update_jd_tool,
    "close_jd":         close_jd_tool,
}

Every tool:
  - Handles pagination via page / page_size params
  - Returns [] / None on empty results (never raises on empty)
  - Wraps transient failures in ToolResult(success=False, error=...)
  - Records latency + status to Prometheus
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.llm_client import LLMClient
from backend.core.schemas import CandidateProfile, JDParsed
from backend.db.models import CandidateModel, JDModel
from backend.observability.telemetry import record_tool_call
from backend.tools.sourcing_tools import (
    search_linkedin as _search_linkedin,
    search_naukri as _search_naukri,
    search_ats as _search_ats,
)
from backend.utils.prometheus_metrics import TOOL_FAILURES

logger = structlog.get_logger()


# ─── Tool Result envelope ─────────────────────────────────────

@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: int = 0
    tool_name: str = ""


def _wrap(tool_name: str):
    """Decorator that records latency + Prometheus metrics for any tool."""
    def decorator(fn):
        async def wrapper(*args, **kwargs) -> ToolResult:
            start = time.monotonic()
            try:
                data = await fn(*args, **kwargs)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                record_tool_call(tool_name, time.monotonic() - start, success=True)
                return ToolResult(success=True, data=data, latency_ms=elapsed_ms, tool_name=tool_name)
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                record_tool_call(tool_name, time.monotonic() - start, success=False)
                TOOL_FAILURES.labels(tool_name=tool_name).inc()
                logger.error("tool_error", tool=tool_name, error=str(exc))
                return ToolResult(success=False, error=str(exc), latency_ms=elapsed_ms, tool_name=tool_name)
        return wrapper
    return decorator


# ─── Source Search Tools ──────────────────────────────────────

@_wrap("search_linkedin")
async def search_linkedin_tool(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Search LinkedIn partition of the HF dataset."""
    results = await _search_linkedin(
        must_have_skills=must_have_skills,
        min_years=min_years,
        page=page,
        page_size=page_size,
    )
    return results or []  # never return None


@_wrap("search_naukri")
async def search_naukri_tool(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Search Naukri partition of the HF dataset."""
    results = await _search_naukri(
        must_have_skills=must_have_skills,
        min_years=min_years,
        page=page,
        page_size=page_size,
    )
    return results or []


@_wrap("search_ats")
async def search_ats_tool(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Search internal ATS partition."""
    results = await _search_ats(
        must_have_skills=must_have_skills,
        min_years=min_years,
        page=page,
        page_size=page_size,
    )
    return results or []


# ─── Profile Fetch Tool ───────────────────────────────────────

@_wrap("fetch_profile")
async def fetch_profile_tool(
    candidate_id: str,
    db: AsyncSession,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single candidate's full profile from the DB.
    Returns None (not an exception) if candidate not found.
    """
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.candidate_id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None
    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "skills": candidate.skills,
        "experience_years": candidate.experience_years,
        "education": candidate.education,
        "employment_history": candidate.employment_history,
        "summary": candidate.summary,
        "source_profiles": candidate.source_profiles,
        "linkedin_url": candidate.linkedin_url,
        "status": candidate.status,
        "screening_data": candidate.screening_data,
        "overall_score": candidate.overall_score,
        "final_rank": candidate.final_rank,
        "outreach_draft": candidate.outreach_draft,
    }


# ─── Score Candidate Tool ─────────────────────────────────────

@_wrap("score_candidate")
async def score_candidate_tool(
    candidate: CandidateProfile,
    jd_parsed: JDParsed,
    llm: LLMClient,
    jd_id: str,
) -> Dict[str, Any]:
    """
    Score a single candidate against JD criteria.
    Wraps the LLM scoring logic as a named tool.
    Returns criterion scores dict or empty dict on failure.
    """
    # Import here to avoid circular dependency
    from backend.agents.screening_agent import ScreeningAgent

    # Build profile text inline (lightweight)
    skills_text = ", ".join(candidate.skills[:15])
    exp_text = f"{candidate.experience_years:.1f} years experience"
    location_text = candidate.location or "unspecified"

    prompt = f"""Score this candidate against the JD criteria. Return JSON with criterion_scores array.
JD: {jd_parsed.title} | Skills needed: {', '.join(jd_parsed.must_have_skills[:5])}
Candidate: {candidate.name} | Skills: {skills_text} | {exp_text} | {location_text}"""

    result = await llm.call_json(
        system_prompt="You are a recruiter scoring candidates. Return JSON: {\"criterion_scores\": [{\"criterion\": str, \"score\": float, \"reasoning\": str}]}",
        user_prompt=prompt,
        agent_name="score_candidate_tool",
        jd_id=jd_id,
        use_flash=True,
    )
    return result


# ─── Draft Outreach Tool ──────────────────────────────────────

@_wrap("draft_outreach")
async def draft_outreach_tool(
    candidate_name: str,
    candidate_skills: List[str],
    jd_title: str,
    jd_skills: List[str],
    llm: LLMClient,
    jd_id: str,
) -> Dict[str, str]:
    """
    Draft a recruiter outreach email for a candidate.
    Returns {"subject": str, "body": str}.
    """
    result = await llm.call_json(
        system_prompt="""Draft a personalized recruiter outreach email (150-200 words).
Return JSON: {"subject": string, "body": string}
Be specific to the candidate's skills. Professional but warm.""",
        user_prompt=f"Candidate: {candidate_name}\nTheir skills: {', '.join(candidate_skills[:8])}\nRole: {jd_title}\nRequired skills: {', '.join(jd_skills[:5])}",
        agent_name="draft_outreach_tool",
        jd_id=jd_id,
        use_flash=True,
    )
    return result or {"subject": f"Opportunity: {jd_title}", "body": f"Hi {candidate_name.split()[0]},\n\nWe'd love to connect about our {jd_title} role.\n\nBest regards"}


# ─── Update JD State Tool ─────────────────────────────────────

@_wrap("update_jd_state")
async def update_jd_state_tool(
    jd_id: str,
    new_status: str,
    db: AsyncSession,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Update JD status in the database.
    Returns True on success, False if JD not found.
    """
    values = {"status": new_status}
    if extra_fields:
        values.update(extra_fields)
    result = await db.execute(
        update(JDModel).where(JDModel.jd_id == jd_id).values(**values)
    )
    return result.rowcount > 0


# ─── Close JD Tool ────────────────────────────────────────────

@_wrap("close_jd")
async def close_jd_tool(
    jd_id: str,
    selected_candidate_id: str,
    recruiter_id: str,
    reason: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Mark JD as closed and selected candidate as SELECTED.
    Returns closure summary dict.
    """
    await db.execute(
        update(JDModel).where(JDModel.jd_id == jd_id).values(status="CLOSED")
    )
    await db.execute(
        update(CandidateModel)
        .where(CandidateModel.candidate_id == selected_candidate_id)
        .values(status="SELECTED")
    )
    return {
        "jd_id": jd_id,
        "selected_candidate_id": selected_candidate_id,
        "recruiter_id": recruiter_id,
        "reason": reason,
        "status": "CLOSED",
    }


# ─── Tool Registry (matches spec's TOOLS dict) ────────────────

TOOLS = {
    "search_linkedin": search_linkedin_tool,
    "search_naukri":   search_naukri_tool,
    "search_ats":      search_ats_tool,
    "fetch_profile":   fetch_profile_tool,
    "score_candidate": score_candidate_tool,
    "draft_outreach":  draft_outreach_tool,
    "update_jd_state": update_jd_state_tool,
    "close_jd":        close_jd_tool,
}


async def call_tool(tool_name: str, **kwargs) -> ToolResult:
    """
    Uniform entry point for all tool calls.
    Agents call this instead of importing tools directly,
    so the registry acts as the single source of truth.
    """
    if tool_name not in TOOLS:
        return ToolResult(success=False, error=f"Unknown tool: {tool_name}", tool_name=tool_name)
    return await TOOLS[tool_name](**kwargs)
