"""
ATS (Applicant Tracking System) MCP Server
============================================
Transport : SSE (HTTP) on port 8003
Tools     : search_profiles, fetch_profile, update_status

The ATS server differs from LinkedIn/Naukri in two important ways:
  1. It has a write tool (update_status) — ATS is the system of record
  2. Its in-memory "database" tracks candidate statuses across calls,
     simulating a real ATS where status changes persist

Backed by the ATS partition (70-100%) of the HuggingFace json_resume_dataset.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from typing import Dict, List, Optional
import mcp.server.fastmcp as fastmcp
from mcp_servers.shared_dataset import filter_profiles, get_partition, normalize

mcp = fastmcp.FastMCP(
    name="ats-mcp",
    instructions=(
        "Internal ATS (Applicant Tracking System) tool. "
        "Use search_profiles to find internal candidates. "
        "Use fetch_profile to get full details. "
        "Use update_status to change a candidate's status in the ATS — "
        "this is the only source that supports status writes."
    ),
)

_ats_status_store: Dict[str, Dict] = {}


@mcp.tool()
async def search_profiles(
    skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """
    Search internal ATS candidates matching a job description.

    Args:
        jd_title:   Job title being recruited for.
        skills:     List of required skill keywords.
        location:   Preferred location (optional).
        min_years:  Minimum years of experience.
        page:       Page number (0-indexed).
        page_size:  Profiles per page (default 50, max 100).

    Returns:
        {
          "source": "ats",
          "page": int,
          "count": int,
          "profiles": [ CandidateProfile, ... ]
        }

    Note: ATS profiles include a "ats_status" field showing current pipeline state.
    """
    await asyncio.sleep(0.1)  # ATS is internal — fastest
    page_size = min(page_size, 100)
    partition = get_partition("ats")
    profiles = filter_profiles(partition, "ats", skills, min_years, page, page_size)

    # Enrich with ATS status if set
    for p in profiles:
        cid = p["candidate_id"]
        if cid in _ats_status_store:
            p["ats_status"] = _ats_status_store[cid]["status"]
            p["ats_updated_at"] = _ats_status_store[cid]["updated_at"]
        else:
            p["ats_status"] = "AVAILABLE"

    return {
        "source": "ats",
        "page": page,
        "count": len(profiles),
        "profiles": profiles,
    }


@mcp.tool()
async def fetch_profile(candidate_id: str) -> dict:
    """
    Fetch a single ATS candidate by candidate ID.

    Args:
        candidate_id: The candidate_id from search_profiles.

    Returns:
        Full CandidateProfile dict with ats_status, or {"error": "not_found"}.
    """
    partition = get_partition("ats")
    for raw in partition:
        profile = normalize(raw, "ats")
        if profile and profile["candidate_id"] == candidate_id:
            status_info = _ats_status_store.get(candidate_id, {})
            profile["ats_status"] = status_info.get("status", "AVAILABLE")
            profile["ats_notes"] = status_info.get("notes", "")
            return profile
    return {"error": "not_found", "candidate_id": candidate_id}


@mcp.tool()
async def update_status(
    candidate_id: str,
    status: str,
    recruiter_id: str,
    notes: Optional[str] = None,
) -> dict:
    """
    Update a candidate's status in the ATS. This is a write operation —
    only the ATS supports status persistence.

    Args:
        candidate_id:  The candidate to update.
        status:        New status. Valid values:
                         AVAILABLE | SCREENING | SHORTLISTED |
                         OUTREACH_SENT | SELECTED | REJECTED | ON_HOLD
        recruiter_id:  ID of the recruiter making the change.
        notes:         Optional notes (e.g. rejection reason).

    Returns:
        {
          "success": bool,
          "candidate_id": str,
          "old_status": str,
          "new_status": str,
          "updated_at": str
        }
    """
    valid_statuses = {
        "AVAILABLE", "SCREENING", "SHORTLISTED",
        "OUTREACH_SENT", "SELECTED", "REJECTED", "ON_HOLD",
    }
    if status.upper() not in valid_statuses:
        return {
            "success": False,
            "error": f"Invalid status '{status}'. Valid: {sorted(valid_statuses)}",
        }

    old_status = _ats_status_store.get(candidate_id, {}).get("status", "AVAILABLE")
    now = datetime.datetime.now(datetime.UTC).isoformat()

    _ats_status_store[candidate_id] = {
        "status": status.upper(),
        "recruiter_id": recruiter_id,
        "notes": notes or "",
        "updated_at": now,
        "old_status": old_status,
    }

    return {
        "success": True,
        "candidate_id": candidate_id,
        "old_status": old_status,
        "new_status": status.upper(),
        "updated_at": now,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8003"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
