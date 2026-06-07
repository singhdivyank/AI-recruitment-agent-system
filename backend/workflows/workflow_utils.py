from typing import Any, Literal

import structlog

from langgraph.graph import END, StateGraph

from backend.agents.compliance_agent import ComplianceAgent
from backend.agents.jd_intake_agent import JDIntakeAgent
from backend.agents.normalization_dedup_agents import DeduplicationAgent, NormalizationAgent
from backend.agents.outreach_closure_agents import OutreachAgent
from backend.agents.ranking_agent import RankingAgent
from backend.agents.screening_agent import ScreeningAgent
from backend.agents.sourcing_agent import SourcingAgent
from backend.core.schemas import WorkflowState
from backend.rag.pipeline import RAGPipeline, get_rag

logger = structlog.get_logger()

# ─── Node wrappers ────────────────────────────────────────────
# LangGraph nodes receive and return the state dict

def make_nodes(agents: dict) -> dict:
    """Return dict of node_name → async callable."""

    async def jd_intake_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["jd_intake"].run(ws)
        return ws.model_dump()

    async def compliance_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["compliance"].run(ws)
        return ws.model_dump()

    async def sourcing_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["sourcing"].run(ws)
        return ws.model_dump()

    async def normalization_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["normalization"].run(ws)
        return ws.model_dump()

    async def deduplication_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["deduplication"].run(ws)
        return ws.model_dump()

    async def rag_ingest_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        rag: RAGPipeline = get_rag()
        logger.info("rag_ingest_start", count=len(ws.deduplicated_profiles))
        await rag.ingest_batch(ws.deduplicated_profiles)
        ws.step = "rag_ingested"
        return ws.model_dump()

    async def screening_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["screening"].run(ws)
        return ws.model_dump()

    async def ranking_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["ranking"].run(ws)
        return ws.model_dump()

    async def outreach_node(state: dict) -> dict:
        ws = WorkflowState(**state)
        ws = await agents["outreach"].run(ws)
        return ws.model_dump()

    return {
        "jd_intake": jd_intake_node,
        "compliance": compliance_node,
        "sourcing": sourcing_node,
        "normalization": normalization_node,
        "deduplication": deduplication_node,
        "rag_ingest": rag_ingest_node,
        "screening": screening_node,
        "ranking": ranking_node,
        "outreach": outreach_node,
    }

# ─── Conditional edges ────────────────────────────────────────

def compliance_router(state: dict) -> Literal["sourcing", "end_rejected"]:
    ws = WorkflowState(**state)
    if ws.error:
        return "end_rejected"
    return "sourcing" if ws.compliance_passed else "end_rejected"


def error_router(state: dict) -> Literal["next", "end_error"]:
    ws = WorkflowState(**state)
    return "end_error" if ws.error else "next"

# ─── Graph Builder ────────────────────────────────────────────

def build_graph(
    llm: Any,
    db: Any,
    rag: RAGPipeline,
) -> Any:
    """
    Build and compile the LangGraph StateGraph.
    Returns a compiled graph ready to invoke.
    """
    agents = {
        "jd_intake": JDIntakeAgent(llm, db),
        "compliance": ComplianceAgent(llm, db),
        "sourcing": SourcingAgent(db),
        "normalization": NormalizationAgent(db),
        "deduplication": DeduplicationAgent(db),
        "screening": ScreeningAgent(llm, db, rag),
        "ranking": RankingAgent(llm, db),
        "outreach": OutreachAgent(llm, db),
    }

    nodes = make_nodes(agents)

    graph = StateGraph(dict)

    # Add all nodes
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # Terminal nodes
    graph.add_node("end_rejected", lambda s: {**s, "step": "rejected"})
    graph.add_node("end_error", lambda s: {**s, "step": "error"})

    # Entry point
    graph.set_entry_point("jd_intake")

    # Linear edges
    graph.add_edge("jd_intake", "compliance")

    # Conditional: compliance pass/fail
    graph.add_conditional_edges(
        "compliance",
        compliance_router,
        {
            "sourcing": "sourcing",
            "end_rejected": "end_rejected",
        },
    )

    graph.add_edge("sourcing", "normalization")
    graph.add_edge("normalization", "deduplication")
    graph.add_edge("deduplication", "rag_ingest")
    graph.add_edge("rag_ingest", "screening")
    graph.add_edge("screening", "ranking")
    graph.add_edge("ranking", "outreach")
    graph.add_edge("outreach", END)
    graph.add_edge("end_rejected", END)
    graph.add_edge("end_error", END)

    return graph.compile()
