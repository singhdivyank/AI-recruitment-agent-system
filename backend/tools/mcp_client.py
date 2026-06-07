"""
MCP Client
===========
Connects to the three MCP servers (LinkedIn, Naukri, ATS) over SSE transport
and exposes a clean async API for the SourcingAgent to call.

This is the boundary between the orchestrator and the MCP protocol.
The SourcingAgent never imports server code directly — it only uses this client.

Architecture:
  SourcingAgent
      │
      ▼
  MCPClient  ──SSE──▶  LinkedIn MCP (port 8001) → search_profiles, fetch_profile
             ──SSE──▶  Naukri MCP   (port 8002) → search_profiles, fetch_profile
             ──SSE──▶  ATS MCP      (port 8003) → search_profiles, fetch_profile, update_status
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

import httpx
import structlog

from backend.core.config import get_settings
from backend.utils.consts import CALL_TOOL_PATH, LIST_TOOLS_PATH

settings = get_settings()
logger = structlog.get_logger()

TIMEOUT = httpx.Timeout(30.0)


class MCPCallError(Exception):
    """Raised when an MCP tool call fails or returns an error result."""


async def _call_tool(
    base_url: str,
    tool_name: str,
    arguments: Dict[str, Any],
    source_label: str,
) -> Any:
    """
    POST to an MCP server's /call_tool endpoint.

    FastMCP over SSE exposes:
      POST /call_tool
      Body: {"name": str, "arguments": dict}
      Response: {"content": [{"type": "text", "text": "<json string>"}]}
                 or {"error": str}
    """
    import json
    url = f"{base_url}{CALL_TOOL_PATH}"
    payload = {"name": tool_name, "arguments": arguments}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # FastMCP wraps the result in content blocks
        if "error" in data:
            raise MCPCallError(f"{source_label}/{tool_name} error: {data['error']}")

        content = data.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return data

    except httpx.HTTPStatusError as exc:
        raise MCPCallError(f"{source_label}/{tool_name} HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise MCPCallError(f"{source_label}/{tool_name} connection error: {exc}") from exc


async def list_tools(base_url: str) -> List[Dict[str, Any]]:
    """List tools exposed by an MCP server (for introspection / health checks)."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{base_url}{LIST_TOOLS_PATH}")
            resp.raise_for_status()
            return resp.json().get("tools", [])
    except Exception as exc:
        logger.warning("mcp_list_tools_failed", url=base_url, error=str(exc))
        return []

async def linkedin_search_profiles(
    jd_title: str,
    skills: List[str],
    location: Optional[str] = None,
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> Dict[str, Any]:
    return await _call_tool(
        settings.linkedin_mcp_url,
        "search_profiles",
        {
            "jd_title": jd_title,
            "skills": skills,
            "location": location,
            "min_years": min_years,
            "page": page,
            "page_size": page_size,
        },
        "linkedin",
    )


async def linkedin_fetch_profile(candidate_id: str) -> Dict[str, Any]:
    return await _call_tool(
        settings.linkedin_mcp_url,
        "fetch_profile",
        {"candidate_id": candidate_id},
        "linkedin",
    )

async def naukri_search_profiles(
    jd_title: str,
    skills: List[str],
    location: Optional[str] = None,
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> Dict[str, Any]:
    return await _call_tool(
        settings.naukri_mcp_url,
        "search_profiles",
        {
            "jd_title": jd_title,
            "skills": skills,
            "location": location,
            "min_years": min_years,
            "page": page,
            "page_size": page_size,
        },
        "naukri",
    )


async def naukri_fetch_profile(candidate_id: str) -> Dict[str, Any]:
    return await _call_tool(
        settings.naukri_mcp_url,
        "fetch_profile",
        {"candidate_id": candidate_id},
        "naukri",
    )

async def ats_search_profiles(
    jd_title: str,
    skills: List[str],
    location: Optional[str] = None,
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> Dict[str, Any]:
    return await _call_tool(
        settings.ats_mcp_url,
        "search_profiles",
        {
            "jd_title": jd_title,
            "skills": skills,
            "location": location,
            "min_years": min_years,
            "page": page,
            "page_size": page_size,
        },
        "ats",
    )


async def ats_fetch_profile(candidate_id: str) -> Dict[str, Any]:
    return await _call_tool(
        settings.ats_mcp_url,
        "fetch_profile",
        {"candidate_id": candidate_id},
        "ats",
    )


async def ats_update_status(
    candidate_id: str,
    status: str,
    recruiter_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Write-back tool — only ATS supports status persistence."""
    return await _call_tool(
        settings.ats_mcp_url,
        "update_status",
        {
            "candidate_id": candidate_id,
            "status": status,
            "recruiter_id": recruiter_id,
            "notes": notes,
        },
        "ats",
    )

async def check_all_servers() -> Dict[str, bool]:
    """Ping all three MCP servers. Used on startup."""
    results = {}
    for name, url in [("linkedin", settings.linkedin_mcp_url), ("naukri", settings.naukri_mcp_url), ("ats", settings.ats_mcp_url)]:
        tools = await list_tools(url)
        results[name] = len(tools) > 0
        logger.info("mcp_health", server=name, ok=results[name], tools=[t.get("name") for t in tools])
    return results
