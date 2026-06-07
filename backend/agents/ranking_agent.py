"""
Ranking Agent
Combines criterion scores into a final weighted score, ranks candidates,
produces top-N shortlist with per-candidate rationale.

Scoring formula:
  final_score = 0.4 * skill_match
              + 0.2 * experience_score
              + 0.2 * semantic_similarity   (from RAG score)
              + 0.1 * location_fit
              + 0.1 * seniority_match
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, Tuple, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from backend.core.llm_client import LLMClient
from backend.core.schemas import (
    CandidateProfile, CandidateStatus, JDParsed,
    RankedCandidate, ScreeningResult, ShortlistResponse, WorkflowState
)
from backend.db.models import CandidateModel, JDModel
from backend.observability.telemetry import observe_agent
from backend.utils.consts import SHORTLIST_N
from backend.utils.helpers import create_rationale_prompt, create_top_pick_prompt
from backend.utils.prompts import RATIONALE_SYSTEM_PROMPT, TOP_PICK_SYSTEM_PROMPT

logger = structlog.get_logger()


class RankingAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession):
        self.llm = llm
        self.db = db
        self.exp_score = 0.0
        self.loc_score = 5.0  # default neutral
        self.seniority_score = 5.0
        self.recruiter_preference = 5.0
    
    def _compute_skill_match(self, screening: ScreeningResult, overrides: Dict):

        must_scores = []
        nice_scores = []

        for cs in screening.criterion_scores:
            crit = cs.criterion.lower()
            # Apply override if recruiter provided one
            effective_score = overrides.get(cs.criterion, cs.score)
            if "must-have" in crit:
                must_scores.append(effective_score)
            elif "nice-to-have" in crit:
                nice_scores.append(effective_score)
            elif "experience" in crit:
                self.exp_score = effective_score
            elif "location" in crit:
                self.loc_score = effective_score

        skill_match = sum(must_scores) / len(must_scores) if must_scores else 0.0
        nice_match = sum(nice_scores) / len(nice_scores) if nice_scores else skill_match * 0.8
        # Must-haves weighted 3x vs nice-to-haves
        self.combined_skill = (skill_match * 3 + nice_match) / 4

    def _compute_final_score(
        self,
        screening: ScreeningResult,
        recruiter_score_overrides: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Decompose criterion scores into the formula components.
        Returns (final_score, breakdown_dict)

        Spec formula:
          final_score = 0.4 * skill_match
                      + 0.2 * experience
                      + 0.2 * semantic_similarity
                      + 0.1 * location_fit
                      + 0.1 * recruiter_preference   ← spec-defined

        recruiter_score_overrides: criterion name → override score (HITL)
        """

        overrides = recruiter_score_overrides or {}

        self._compute_skill_match(screening=screening, overrides=overrides)
        if overrides:
            self.recruiter_preference = min(10.0, sum(overrides.values()) / len(overrides))

        breakdown = {
            "skill_match": round(self.combined_skill, 2),
            "experience_score": round(self.exp_score, 2),
            "semantic_similarity": round(screening.overall_score, 2),
            "location_fit": round(self.loc_score, 2),
            "recruiter_preference": round(self.recruiter_preference, 2),
        }

        final = (
            0.40 * breakdown["skill_match"]
            + 0.20 * breakdown["experience_score"]
            + 0.20 * breakdown["semantic_similarity"]
            + 0.10 * breakdown["location_fit"]
            + 0.10 * breakdown["recruiter_preference"]
        )
        return round(min(final, 10.0), 2), breakdown

    async def _generate_rationale(
        self,
        candidate: CandidateProfile,
        screening: ScreeningResult,
        jd_parsed: Optional[JDParsed],
        jd_id: str,
    ) -> str:
        
        if not jd_parsed:
            return screening.screening_summary
        
        user_prompt = create_rationale_prompt(
            jd_parsed=jd_parsed, 
            candidate=candidate, 
            screening=screening
        )
        try:
            return await self.llm.call_with_retry(
                system_prompt=RATIONALE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name="ranking_agent",
                jd_id=jd_id,
                use_flash=True,   # Flash sufficient for rationale generation
            )
        except Exception:
            return screening.screening_summary

    @observe_agent("ranking_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd_id = state.jd_id
        jd_parsed: Optional[JDParsed] = state.jd_parsed
        screening_results = state.screening_results
        log = logger.bind(agent="ranking", jd_id=jd_id)
        log.info("start", screening_count=len(screening_results))

        profile_map = {p.candidate_id: p for p in state.deduplicated_profiles}

        # Compute final scores
        scored: List[Tuple[float, Dict, CandidateProfile, ScreeningResult]] = []
        for sr in screening_results:
            profile = profile_map.get(sr.candidate_id)
            if not profile:
                continue
            final_score, breakdown = self._compute_final_score(sr)
            scored.append((final_score, breakdown, profile, sr))

        # Sort descending
        scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored[:SHORTLIST_N]

        # ── Generate rationale for each shortlisted candidate (parallel) ──
        sem = asyncio.Semaphore(3)

        async def gen_rationale(item):
            final_score, breakdown, profile, sr = item
            async with sem:
                rationale = await self._generate_rationale(profile, sr, jd_parsed, jd_id)
            return final_score, breakdown, profile, sr, rationale

        rationale_results = await asyncio.gather(
            *[gen_rationale(item) for item in top_candidates],
            return_exceptions=True,
        )

        ranked_candidates: List[RankedCandidate] = []
        for rank, result in enumerate(rationale_results, 1):
            if isinstance(result, Exception):
                log.error("rationale_failed", rank=rank, error=str(result))
                continue
            final_score, breakdown, profile, sr, rationale = result
            ranked_candidates.append(RankedCandidate(
                rank=rank,
                candidate=profile,
                screening=sr,
                final_score=final_score,
                score_breakdown=breakdown,
                rationale=rationale,
            ))

        # ── Top Pick Selection ──────────────────────────────────
        top_pick_id, justification = await self._select_top_pick(ranked_candidates, jd_parsed, jd_id)
        top_pick = next(
            (rc for rc in ranked_candidates if rc.candidate.candidate_id == top_pick_id),
            ranked_candidates[0] if ranked_candidates else None,
        )

        shortlist = ShortlistResponse(
            jd_id=jd_id,
            shortlist=ranked_candidates,
            top_pick=top_pick,
            top_pick_justification=justification,
            total_candidates_evaluated=len(screening_results),
        )

        # Persist ranking to DB
        for rc in ranked_candidates:
            await self.db.execute(
                update(CandidateModel)
                .where(CandidateModel.candidate_id == rc.candidate.candidate_id)
                .values(
                    final_rank=rc.rank,
                    status=CandidateStatus.SHORTLISTED.value,
                    overall_score=rc.final_score,
                )
            )

        # Update JD status
        await self.db.execute(
            update(JDModel)
            .where(JDModel.jd_id == jd_id)
            .values(status="SHORTLISTED")
        )

        log.info("ranking_complete", shortlisted=len(ranked_candidates), top_pick=top_pick.candidate.name if top_pick else "none")
        state.shortlist = shortlist
        state.step = "ranked"
        return state

    async def _select_top_pick(
        self,
        ranked: List[RankedCandidate],
        jd_parsed: Optional[JDParsed],
        jd_id: str,
    ) -> Tuple[str, str]:
        
        if not jd_parsed:
            return "", "No JD parsed"

        if not ranked:
            return "", "No candidates to rank."

        shortlist_text = "\n\n".join([
            f"Rank #{rc.rank} | Score: {rc.final_score}/10 | {rc.candidate.name}\n"
            f"  Skills: {', '.join(rc.candidate.skills[:8])}\n"
            f"  YOE: {rc.candidate.experience_years:.1f} | Location: {rc.candidate.location}\n"
            f"  Rationale: {rc.rationale}\n"
            f"  Candidate ID: {rc.candidate.candidate_id}"
            for rc in ranked[:5]
        ])

        user_prompt = create_top_pick_prompt(jd_parsed=jd_parsed, shortlist_text=shortlist_text)
        try:
            result = await self.llm.call_json(
                system_prompt=TOP_PICK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name="ranking_agent",
                jd_id=jd_id,
                use_flash=False,
            )
            return result["top_candidate_id"], result["justification"]
        except Exception as exc:
            logger.error("top_pick_failed", error=str(exc))
            return ranked[0].candidate.candidate_id, ranked[0].rationale
