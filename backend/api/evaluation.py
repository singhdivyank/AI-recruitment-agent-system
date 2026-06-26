"""
Evaluation metrics endpoint.

Implements the metrics from the spec:
  Component     | Metric
  --------------|------------------------------------------
  Retrieval     | Recall@10, Precision@10, NDCG@10
  Deduplication | Precision, Recall, F1
  Screening     | Human Agreement %, MAE vs recruiter scores
  Ranking       | Top-1 Accuracy, NDCG@10
  Agent Workflow | Completion Rate, Tool Success Rate
  Cost          | Tokens/JD, Cost/JD
  Latency       | Time-to-Shortlist
"""
from __future__ import annotations
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from db.models import AuditModel, CandidateModel, JDModel, RecruiterFeedbackModel
from db.session import get_db
from utils.helpers import _ndcg_at_k, _precision_at_k, _recall_at_k, _comp_ai_score

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])

@router.get("/retrieval/{jd_id}")
async def retrieval_metrics(
    jd_id: str,
    k: int = 10,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieval Recall@k, Precision@k, NDCG@k for a JD.
    Uses overall_score as the relevance signal.
    """
    result = await db.execute(
        select(CandidateModel)
        .where(CandidateModel.jd_id == jd_id)
        .where(CandidateModel.overall_score.isnot(None))
        .order_by(CandidateModel.final_rank.asc().nullslast())
    )
    candidates = result.scalars().all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No screened candidates for this JD")

    scores = [float(c.overall_score or 0) for c in candidates]

    return {
        "jd_id": jd_id,
        "k": k,
        "total_candidates": len(candidates),
        "retrieval": {
            f"precision_at_{k}": round(_precision_at_k(scores, k), 4),
            f"recall_at_{k}": round(_recall_at_k(scores, k), 4),
            f"ndcg_at_{k}": round(_ndcg_at_k(scores, k), 4),
        },
    }

@router.get("/deduplication/{jd_id}")
async def deduplication_metrics(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Deduplication quality metrics.
    Uses source_profiles count as a proxy: a candidate with 2+ sources was a cross-source duplicate.
    Precision = candidates correctly merged / candidates that should have been merged.
    """
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.jd_id == jd_id)
    )
    candidates = result.scalars().all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates for this JD")

    total = len(candidates)
    merged = sum(1 for c in candidates if len(c.source_profiles or []) > 1)
    unique_sources_per_candidate = [
        len(set(sp.get("source") for sp in (c.source_profiles or [])))
        for c in candidates
    ]
    avg_sources = sum(unique_sources_per_candidate) / total if total else 0

    # Estimate: without dedup, we'd have source_profiles.count total records
    total_raw_records = sum(len(c.source_profiles or [1]) for c in candidates)
    records_merged = total_raw_records - total
    merge_rate = records_merged / total_raw_records if total_raw_records > 0 else 0

    return {
        "jd_id": jd_id,
        "deduplication": {
            "total_unique_candidates": total,
            "candidates_from_multiple_sources": merged,
            "total_raw_records_before_dedup": total_raw_records,
            "records_merged": records_merged,
            "merge_rate": round(merge_rate, 4),
            "avg_sources_per_candidate": round(avg_sources, 2),
        },
        "note": "F1 requires ground-truth labels. merge_rate approximates dedup recall.",
    }

@router.get("/screening/{jd_id}")
async def screening_metrics(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Screening vs recruiter agreement.
    Compares AI scores vs recruiter override scores where overrides exist.
    MAE = mean absolute error between AI score and recruiter score.
    Agreement % = fraction where |AI - human| <= 1.5 points (on 0-10 scale).
    """
    
    errors, agreements = [], []

    result = await db.execute(
        select(RecruiterFeedbackModel).where(RecruiterFeedbackModel.jd_id == jd_id)
    )
    feedbacks = result.scalars().all()

    if not feedbacks:
        return {
            "jd_id": jd_id,
            "screening": {
                "overrides_count": 0,
                "mae": None,
                "agreement_pct": None,
                "note": "No recruiter overrides recorded yet.",
            },
        }

    for fb in feedbacks:
        # Get the candidate's AI scores for the overridden criteria
        cand_result = await db.execute(
            select(CandidateModel).where(CandidateModel.candidate_id == fb.candidate_id)
        )
        candidate = cand_result.scalar_one_or_none()
        if not candidate or not candidate.screening_data:
            continue
        agree, error = _comp_ai_score(candidate=candidate, fb=fb)
        agreements.extend(agree)
        errors.extend(error)

    mae = sum(errors) / len(errors) if errors else None
    agreement_pct = (sum(agreements) / len(agreements) * 100) if agreements else None

    return {
        "jd_id": jd_id,
        "screening": {
            "overrides_count": len(feedbacks),
            "criteria_overridden": len(errors),
            "mae": round(mae, 3) if mae is not None else None,
            "agreement_pct": round(agreement_pct, 1) if agreement_pct is not None else None,
        },
    }

@router.get("/ranking/{jd_id}")
async def ranking_metrics(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Ranking Top-1 Accuracy and NDCG@10.
    Top-1 Accuracy: 1 if the selected candidate was ranked #1, else 0.
    """
    # Get shortlisted candidates in rank order
    result = await db.execute(
        select(CandidateModel)
        .where(CandidateModel.jd_id == jd_id)
        .where(CandidateModel.final_rank.isnot(None))
        .order_by(CandidateModel.final_rank.asc())
    )
    ranked = result.scalars().all()

    # Get selected candidate (from audit)
    audit_result = await db.execute(
        select(AuditModel)
        .where(AuditModel.jd_id == jd_id)
        .where(AuditModel.action == "JD_CLOSED")
    )
    closure = audit_result.scalar_one_or_none()

    top1_accuracy = None
    if closure and ranked:
        top1_accuracy = 1.0 if ranked[0].candidate_id == closure.selected_candidate_id else 0.0

    scores = [float(c.overall_score or 0) for c in ranked]
    ndcg = _ndcg_at_k(scores, 10) if len(scores) >= 2 else None

    return {
        "jd_id": jd_id,
        "ranking": {
            "shortlisted_count": len(ranked),
            "top_1_accuracy": top1_accuracy,
            f"ndcg_at_10": round(ndcg, 4) if ndcg is not None else None,
            "selected_candidate_id": closure.selected_candidate_id if closure else None,
            "top_ranked_candidate_id": ranked[0].candidate_id if ranked else None,
        },
    }

@router.get("/workflow")
async def workflow_metrics(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Agent workflow completion rate and overall pipeline stats.
    """
    total_result = await db.execute(select(func.count(JDModel.jd_id)))
    closed_result = await db.execute(
        select(func.count(JDModel.jd_id)).where(JDModel.status == "CLOSED")
    )
    rejected_result = await db.execute(
        select(func.count(JDModel.jd_id)).where(JDModel.status == "REJECTED")
    )
    cost_result = await db.execute(
        select(func.avg(JDModel.estimated_cost_usd)).where(JDModel.status == "CLOSED")
    )
    
    total_jds = total_result.scalar() or 0
    closed_jds = closed_result.scalar() or 0
    completion_rate = closed_jds / total_jds if total_jds > 0 else 0.0

    return {
        "workflow": {
            "total_jds": total_jds,
            "closed_jds": closed_jds,
            "rejected_jds": rejected_result.scalar() or 0,
            "completion_rate": round(completion_rate, 4),
            "avg_cost_per_jd_usd": round(float(cost_result.scalar() or 0.0), 4),
        },
    }

@router.get("/cost/{jd_id}")
async def cost_metrics(jd_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Token/JD and Cost/JD breakdown."""
    result = await db.execute(select(JDModel).where(JDModel.jd_id == jd_id))
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    candidates_result = await db.execute(
        select(func.count(CandidateModel.candidate_id)).where(CandidateModel.jd_id == jd_id)
    )
    candidate_count = candidates_result.scalar() or 0

    total_tokens = (jd.total_input_tokens or 0) + (jd.total_output_tokens or 0)
    cost_per_candidate = (
        jd.estimated_cost_usd / candidate_count if candidate_count > 0 else 0
    )

    return {
        "jd_id": jd_id,
        "cost": {
            "total_tokens": total_tokens,
            "input_tokens": jd.total_input_tokens or 0,
            "output_tokens": jd.total_output_tokens or 0,
            "estimated_cost_usd": jd.estimated_cost_usd or 0.0,
            "candidates_evaluated": candidate_count,
            "cost_per_candidate_usd": round(cost_per_candidate, 6),
        },
    }
