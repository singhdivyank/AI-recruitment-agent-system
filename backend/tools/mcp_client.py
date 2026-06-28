"""
MCP Client
===========
Connects to the three MCP servers (LinkedIn, Naukri, ATS) over SSE transport
using the official MCP Python SDK client.
 
FastMCP's SSE transport exposes two endpoints:
  GET  /sse          — SSE stream (tool calls go through here)
  POST /messages/    — message posting endpoint
 
There is NO plain HTTP /call_tool or /tools REST endpoint.
All tool invocations go through the MCP protocol over the SSE stream.
 
Architecture:
  SourcingAgent → MCPClient → MCP SDK ClientSession → SSE → MCP Server
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

import structlog

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent

from core.config import get_settings
from core.schemas import MCPCallError

settings = get_settings()
logger = structlog.get_logger()


async def _call_tool(
    base_url: str,
    tool_name: str,
    arguments: Dict[str, Any],
    source_label: str,
) -> Any:
    """
    Call a tool on an MCP server over SSE transport using the MCP SDK.
    Opens a short-lived session per call (stateless usage pattern).
    """
    import json
    sse_url = f"{base_url}/sse"

    try:
        async with sse_client(sse_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)

        # FastMCP wraps the result in content blocks
        if result.isError:
            raise MCPCallError(f"{source_label}/{tool_name} tool error: {result.content}")

        content = result.content[0]
        if content and isinstance(content, TextContent):
            text = content.text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        
        return {}

    except MCPCallError:
        raise
    except Exception as exc:
        raise MCPCallError(f"{source_label}/{tool_name} connection error: {exc}") from exc


async def list_tools(base_url: str) -> List[Dict[str, Any]]:
    """List tools exposed by an MCP server (for introspection / health checks)."""
    try:
        sse_url = f"{base_url}/sse"
        async with sse_client(sse_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [{"name": t.name, "description": t.description} for t in result.tools]
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
