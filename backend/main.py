"""
FastAPI Application Entry Point
Includes all routers, middleware, startup/shutdown lifecycle,
and Prometheus + OTel instrumentation.
"""
from __future__ import annotations
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .agents.outreach_closure_agents import ClosureAgent
from .api.evaluation import router as eval_router
from .core.config import get_settings
from .core.llm_client import LLMClient
from .core.schemas import (
    ConversationMessage, 
    JDCloseRequest, 
    JDCreate, 
    ScoreOverrideRequest,
    WorkflowState,
    OutreachSendRequest
)
from .db.models import (
    AuditModel, 
    CandidateModel, 
    ConversationModel,
    JDModel,
    RecruiterFeedbackModel, 
    OutreachHistoryModel
)
from .db.session import get_db, init_db
from .observability.telemetry import setup_prometheus, setup_tracing
from .rag.pipeline import get_rag
from .tools.mcp_client import check_all_servers
from .utils.helpers import _audit_to_dict, _jd_to_dict, _candidate_to_dict
from .utils.prompts import CONVERSATION_TURN_PROMPT
from .workflows.orchestrator import OrchestratorAgent

settings = get_settings()
logger = structlog.get_logger()

# Module-level Redis client
_redis: Optional[aioredis.Redis] = None

def get_redis() -> aioredis.Redis:
    return _redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _redis

    # Set LangSmith env vars before anything else
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    # Init OTel tracing
    setup_tracing()
    logger.info("startup", env=settings.app_env)

    # Init DB
    await init_db()
    logger.info("database_initialized")

    # Init Redis
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await _redis.ping()
    logger.info("redis_connected")

    # Warm up RAG (loads models)
    _ = get_rag()
    logger.info("rag_warmed_up")

    # Health-check all three MCP servers
    mcp_status = await check_all_servers()
    logger.info("mcp_servers_health", status=mcp_status)

    yield

    # Shutdown
    if _redis:
        await _redis.close()
    logger.info("shutdown")


app = FastAPI(
    title="AI Recruitment Agent",
    description="End-to-end multi-agent recruitment automation system",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_prometheus(app)

def get_llm(redis=Depends(get_redis)) -> LLMClient:
    return LLMClient(redis_client=redis)

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/v1/jds", response_model=Dict[str, Any], tags=["jd"])
async def create_jd(
    jd: JDCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """
    Submit a new Job Description.
    Triggers the full multi-agent pipeline asynchronously.
    Returns immediately with jd_id for status polling.
    """
    jd_id = str(uuid.uuid4())
    initial_state = WorkflowState(jd_id=jd_id, jd_raw=jd)

    rag = get_rag()
    orchestrator = OrchestratorAgent(llm, db, rag)

    # Run pipeline in background so client gets immediate response
    background_tasks.add_task(_run_pipeline, orchestrator, initial_state, db)

    logger.info("jd_submitted", jd_id=jd_id, title=jd.title)
    return {
        "jd_id": jd_id,
        "status": "PROCESSING",
        "message": "JD submitted. Pipeline started.",
    }


async def _run_pipeline(orchestrator: OrchestratorAgent, state: WorkflowState, db: AsyncSession):
    """Background task: run full workflow."""
    try:
        await orchestrator.run_workflow(state)
        await db.commit()
    except Exception as exc:
        logger.error("pipeline_error", jd_id=state.jd_id, error=str(exc))
        await db.rollback()


@app.get("/api/v1/jds", tags=["jd"])
async def list_jds(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all JDs with optional status filter."""
    stmt = select(JDModel).offset(offset).limit(limit)
    if status:
        stmt = stmt.where(JDModel.status == status.upper())
    result = await db.execute(stmt)
    jds = result.scalars().all()
    return {
        "items": [_jd_to_dict(j) for j in jds],
        "total": len(jds),
    }


@app.get("/api/v1/jds/{jd_id}", tags=["jd"])
async def get_jd(jd_id: str, db: AsyncSession = Depends(get_db)):
    """Get full JD detail including parsed data and candidate counts."""
    result = await db.execute(select(JDModel).where(JDModel.jd_id == jd_id))
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    # Count candidates
    count_result = await db.execute(
        select(CandidateModel).where(CandidateModel.jd_id == jd_id)
    )
    candidates = count_result.scalars().all()
    shortlisted = [c for c in candidates if c.status in ("SHORTLISTED", "SELECTED")]

    return {
        **_jd_to_dict(jd),
        "total_candidates": len(candidates),
        "shortlisted_count": len(shortlisted),
    }


@app.get("/api/v1/jds/{jd_id}/shortlist", tags=["jd"])
async def get_shortlist(jd_id: str, db: AsyncSession = Depends(get_db)):
    """Get the ranked shortlist for a JD."""
    result = await db.execute(
        select(CandidateModel)
        .where(CandidateModel.jd_id == jd_id)
        .where(CandidateModel.final_rank.isnot(None))
        .order_by(CandidateModel.final_rank)
    )
    candidates = result.scalars().all()
    if not candidates:
        raise HTTPException(status_code=404, detail="Shortlist not ready yet")
    return {"jd_id": jd_id, "shortlist": [_candidate_to_dict(c) for c in candidates]}


@app.post("/api/v1/jds/{jd_id}/close", tags=["jd"])
async def close_jd(
    jd_id: str,
    req: JDCloseRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """Close a JD with the selected candidate."""
    # Validate JD exists
    jd_result = await db.execute(select(JDModel).where(JDModel.jd_id == jd_id))
    jd = jd_result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    # Get selected candidate snapshot
    cand_result = await db.execute(
        select(CandidateModel).where(CandidateModel.candidate_id == req.selected_candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    snapshot = _candidate_to_dict(candidate)
    closure_agent = ClosureAgent(llm, db)
    audit = await closure_agent.close(req, snapshot)
    await db.commit()

    return {
        "jd_id": jd_id,
        "status": "CLOSED",
        "audit_id": audit.audit_id,
        "selected_candidate": candidate.name,
        "closed_at": str(audit.closed_at),
    }

@app.get("/api/v1/jds/{jd_id}/candidates", tags=["candidates"])
async def list_candidates(
    jd_id: str,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CandidateModel).where(CandidateModel.jd_id == jd_id)
    if status:
        stmt = stmt.where(CandidateModel.status == status.upper())
    result = await db.execute(stmt)
    candidates = result.scalars().all()
    return {"candidates": [_candidate_to_dict(c) for c in candidates]}


@app.get("/api/v1/candidates/{candidate_id}", tags=["candidates"])
async def get_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.candidate_id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _candidate_to_dict(candidate)

@app.get("/api/v1/jds/{jd_id}/audit", tags=["audit"])
async def get_audit_log(jd_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditModel)
        .where(AuditModel.jd_id == jd_id)
        .order_by(AuditModel.closed_at)
    )
    records = result.scalars().all()
    return {"jd_id": jd_id, "audit_log": [_audit_to_dict(r) for r in records]}

@app.get("/api/v1/metrics/cost", tags=["observability"])
async def get_cost_stats(redis=Depends(get_redis)):
    daily = await redis.get("cost:daily") or "0"
    return {
        "daily_cost_usd": round(float(daily), 4),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(float(daily) / settings.daily_budget_usd * 100, 1),
    }

@app.post("/api/v1/jds/{jd_id}/candidates/{candidate_id}/override", tags=["hitl"])
async def override_candidate_scores(
    jd_id: str,
    candidate_id: str,
    req: ScoreOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    HITL: Recruiter overrides AI-assigned criterion scores.
    Overrides are applied on next ranking pass and stored in audit trail.
    """
    # Upsert feedback record
    from sqlalchemy import select as _sel
    existing = await db.execute(
        _sel(RecruiterFeedbackModel)
        .where(RecruiterFeedbackModel.jd_id == jd_id)
        .where(RecruiterFeedbackModel.candidate_id == candidate_id)
        .where(RecruiterFeedbackModel.recruiter_id == req.recruiter_id)
    )
    fb = existing.scalar_one_or_none()
    if fb:
        fb.score_overrides = req.score_overrides
        fb.weight_overrides = req.weight_overrides
        fb.notes = req.notes
        fb.decision = req.decision
    else:
        fb = RecruiterFeedbackModel(
            jd_id=jd_id,
            candidate_id=candidate_id,
            recruiter_id=req.recruiter_id,
            score_overrides=req.score_overrides,
            weight_overrides=req.weight_overrides,
            notes=req.notes,
            decision=req.decision,
        )
        db.add(fb)

    # Update candidate model
    from sqlalchemy import update as _upd
    await db.execute(
        _upd(CandidateModel)
        .where(CandidateModel.candidate_id == candidate_id)
        .values(
            recruiter_score_overrides=req.score_overrides,
            recruiter_weight_overrides=req.weight_overrides,
            recruiter_notes=req.notes,
        )
    )

    # Audit entry
    db.add(AuditModel(
        jd_id=jd_id,
        recruiter_id=req.recruiter_id,
        action="SCORE_OVERRIDDEN",
        metadata={
            "candidate_id": candidate_id,
            "overrides": req.score_overrides,
            "decision": req.decision,
        },
    ))
    await db.commit()

    logger.info("score_overridden", jd_id=jd_id, candidate_id=candidate_id, recruiter=req.recruiter_id)
    return {"status": "ok", "message": "Overrides saved. Re-run ranking to apply."}


@app.post("/api/v1/jds/{jd_id}/conversation", tags=["conversation"])
async def add_conversation_turn(
    jd_id: str,
    msg: ConversationMessage,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """
    Multi-turn conversational refinement for a JD.
    Recruiter can ask follow-up questions like 'show me only remote candidates'
    and the system responds with updated context.
    """
    # Persist user turn
    db.add(ConversationModel(
        jd_id=jd_id,
        recruiter_id=msg.recruiter_id,
        role="user",
        content=msg.content,
    ))

    # Load conversation history
    from sqlalchemy import select as _sel
    hist_result = await db.execute(
        _sel(ConversationModel)
        .where(ConversationModel.jd_id == jd_id)
        .order_by(ConversationModel.created_at.asc())
        .limit(20)
    )
    history = hist_result.scalars().all()

    history_text = "\n".join([f"{h.role.upper()}: {h.content}" for h in history])
    jd_result = await db.execute(select(JDModel).where(JDModel.jd_id == jd_id))
    jd = jd_result.scalar_one_or_none()

    response = await llm.call_with_retry(
        system_prompt=CONVERSATION_TURN_PROMPT,
        user_prompt=f"JD: {jd.title if jd else jd_id}\n\nConversation:\n{history_text}\n\nRespond to the latest recruiter message.",
        agent_name="conversation_agent",
        jd_id=jd_id,
        use_flash=True,
    )

    # Persist assistant response
    db.add(ConversationModel(
        jd_id=jd_id,
        recruiter_id="system",
        role="assistant",
        content=response,
    ))
    await db.commit()

    return {"role": "assistant", "content": response}


@app.get("/api/v1/jds/{jd_id}/conversation", tags=["conversation"])
async def get_conversation(jd_id: str, db: AsyncSession = Depends(get_db)):
    """Get full conversation history for a JD."""
    from sqlalchemy import select as _sel
    result = await db.execute(
        _sel(ConversationModel)
        .where(ConversationModel.jd_id == jd_id)
        .order_by(ConversationModel.created_at.asc())
    )
    turns = result.scalars().all()
    return {
        "jd_id": jd_id,
        "conversation": [
            {"role": t.role, "content": t.content, "created_at": str(t.created_at)}
            for t in turns
        ],
    }

@app.post("/api/v1/candidates/{candidate_id}/outreach", tags=["outreach"])
async def send_outreach(
    candidate_id: str,
    req: OutreachSendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record that outreach was sent to a candidate (persists to outreach_history)."""
    from sqlalchemy import select as _sel

    cand_result = await db.execute(
        _sel(CandidateModel).where(CandidateModel.candidate_id == candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    record = OutreachHistoryModel(
        candidate_id=candidate_id,
        jd_id=candidate.jd_id,
        recruiter_id=req.recruiter_id,
        subject=req.subject,
        body=req.body,
        channel=req.channel,
        sent_at=datetime.utcnow(),
    )
    db.add(record)
    # Update candidate sent timestamp
    from sqlalchemy import update as _upd
    await db.execute(
        _upd(CandidateModel)
        .where(CandidateModel.candidate_id == candidate_id)
        .values(outreach_sent_at=datetime.utcnow(), status="OUTREACH_SENT")
    )
    await db.commit()
    return {"status": "ok", "outreach_id": record.outreach_id}


@app.get("/api/v1/candidates/{candidate_id}/outreach", tags=["outreach"])
async def get_outreach_history(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Get full outreach history for a candidate."""
    from sqlalchemy import select as _sel
    result = await db.execute(
        _sel(OutreachHistoryModel)
        .where(OutreachHistoryModel.candidate_id == candidate_id)
        .order_by(OutreachHistoryModel.sent_at.desc())
    )
    return {
        "candidate_id": candidate_id,
        "outreach_history": [
            {
                "outreach_id": r.outreach_id,
                "subject": r.subject,
                "channel": r.channel,
                "sent_at": str(r.sent_at),
                "response_received": r.response_received,
                "response_text": r.response_text,
            }
            for r in result.scalars().all()
        ],
    }

app.include_router(eval_router)
