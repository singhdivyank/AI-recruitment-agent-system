"""
Naukri MCP Server
==================
Transport : SSE (HTTP) on port 8002
Tools     : search_profiles, fetch_profile

Backed by the Naukri partition (38–70%) of the HuggingFace json_resume_dataset.
The 2% overlap with LinkedIn is intentional to generate cross-source duplicates
that the Deduplication Agent must resolve.

Naukri returns profiles in a slightly different field order and with different
latency characteristics to simulate realistic source heterogeneity.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List
import mcp.server.fastmcp as fastmcp
from mcp_servers.shared_dataset import filter_profiles, get_partition, normalize

mcp = fastmcp.FastMCP(
    name="naukri-mcp",
    instructions=(
        "Naukri.com profile search tool. "
        "Use search_profiles to find candidates. "
        "Use fetch_profile to retrieve a single candidate by ID."
    ),
)


@mcp.tool()
async def search_profiles(
    skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """
    Search Naukri profiles matching a job description.

    Args:
        jd_title:   Job title being recruited for.
        skills:     List of required skill keywords.
        location:   Preferred location (optional).
        min_years:  Minimum years of experience.
        page:       Page number (0-indexed).
        page_size:  Profiles per page (default 50, max 100).

    Returns:
        {
          "source": "naukri",
          "page": int,
          "count": int,
          "profiles": [ CandidateProfile, ... ]
        }
    """
    await asyncio.sleep(0.35)
    page_size = min(page_size, 100)
    partition = get_partition("naukri")
    profiles = filter_profiles(partition, "naukri", skills, min_years, page, page_size)
    
    return {
        "source": "naukri",
        "page": page,
        "count": len(profiles),
        "profiles": profiles,
    }


@mcp.tool()
async def fetch_profile(candidate_id: str) -> dict:
    """
    Fetch a single Naukri profile by candidate ID.

    Args:
        candidate_id: The candidate_id from search_profiles.

    Returns:
        Full CandidateProfile dict or {"error": "not_found"}.
    """
    partition = get_partition("naukri")
    
    for raw in partition:
        profile = normalize(raw, "naukri")
        if profile and profile["candidate_id"] == candidate_id:
            return profile
    
    return {"error": "not_found", "candidate_id": candidate_id}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
