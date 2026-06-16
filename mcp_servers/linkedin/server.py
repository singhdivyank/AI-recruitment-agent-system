"""
LinkedIn MCP Server
====================
Transport : SSE (HTTP) on port 8001
Tools     : search_profiles, fetch_profile

Backed by the LinkedIn partition (0–40%) of the HuggingFace json_resume_dataset.

The agent calls this server over HTTP exactly like it would call a real
LinkedIn integration. The MCP protocol handles tool discovery, schema
validation, and serialisation — the agent never imports this module directly.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List
import mcp.server.fastmcp as fastmcp
from mcp_servers.shared_dataset import filter_profiles, get_partition, normalize

mcp = fastmcp.FastMCP(
    name="linkedin-mcp",
    instructions=(
        "LinkedIn profile search tool. "
        "Use search_profiles to find candidates matching a JD. "
        "Use fetch_profile to retrieve a single candidate by ID."
    ),
    host="0.0.0.0", 
    port=int(os.getenv("PORT", "8001"))
)

@mcp.tool()
async def search_profiles(
    skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """
    Search LinkedIn profiles matching a job description.

    Args:
        jd_title:   Job title being recruited for.
        skills:     List of required skill keywords.
        location:   Preferred location (optional).
        min_years:  Minimum years of experience required.
        page:       Page number for pagination (0-indexed).
        page_size:  Profiles per page (default 50, max 100).

    Returns:
        {
          "source": "linkedin",
          "page": int,
          "count": int,
          "profiles": [ CandidateProfile, ... ]
        }
    """
    await asyncio.sleep(0.2)
    page_size = min(page_size, 100)
    partition = get_partition("linkedin")
    profiles = filter_profiles(partition, "linkedin", skills, min_years, page, page_size)
    return {
        "source": "linkedin",
        "page": page,
        "count": len(profiles),
        "profiles": profiles,
    }

@mcp.tool()
async def fetch_profile(candidate_id: str) -> dict:
    """
    Fetch a single LinkedIn profile by candidate ID.

    Args:
        candidate_id: The candidate_id returned by search_profiles.

    Returns:
        The full CandidateProfile dict, or {"error": "not_found"}.
    """
    partition = get_partition("linkedin")

    for raw in partition:
        profile = normalize(raw, "linkedin")
        if profile and profile["candidate_id"] == candidate_id:
            return profile
    
    return {"error": "not_found", "candidate_id": candidate_id}

if __name__ == "__main__":
    mcp.run(transport="sse")
