"""
LangGraph Orchestrator
Defines the full multi-agent workflow as a directed state graph.

Graph topology (fan-out / fan-in):
  JD_INTAKE → COMPLIANCE → [pass/fail] → SOURCING → NORMALIZATION
  → DEDUPLICATION → RAG_INGEST → SCREENING → RANKING → OUTREACH → END

Each node is a specialist agent. LangGraph manages state passing.
Parallel sourcing is handled inside the SourcingAgent via asyncio.gather.
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .workflow_utils import build_graph
from core.llm_client import LLMClient
from core.schemas import WorkflowState
from rag.pipeline import RAGPipeline

logger = structlog.get_logger()


class OrchestratorAgent:
    """
    High-level orchestrator: builds the graph, runs it,
    tracks progress, and returns the final WorkflowState.
    """

    def __init__(self, llm: LLMClient, db: AsyncSession, rag: RAGPipeline):
        self.llm = llm
        self.db = db
        self.rag = rag
        self._graph = build_graph(llm, db, rag)

    async def run_workflow(self, initial_state: WorkflowState) -> WorkflowState:
        log = logger.bind(jd_id=initial_state.jd_id)
        log.info("workflow_start")

        state_dict = initial_state.model_dump()
        final_state_dict = await self._graph.ainvoke(state_dict)
        final = WorkflowState(**final_state_dict)

        log.info(
            "workflow_complete",
            step=final.step,
            candidates_screened=len(final.screening_results),
            shortlisted=len(final.shortlist.shortlist) if final.shortlist else 0,
            cost_usd=round(final.estimated_cost_usd, 4),
        )
        return final
