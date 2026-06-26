"""
Screening Agent
Per-criterion scoring with LLM reasoning for each candidate.
Uses RAG retrieval to identify the most relevant candidates first,
then screens the top candidates in a second fan-out.

Scoring criteria come from the parsed JD:
  - Must-have skills (weighted 2x)
  - Nice-to-have skills
  - Years of experience
  - Location fit
  - Seniority match
"""
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_client import LLMClient
from core.schemas import (
    CandidateProfile, 
    CandidateStatus, 
    CriterionScore,
    JDParsed, 
    ScreeningResult, 
    WorkflowState,
)
from db.models import CandidateModel
from observability.telemetry import observe_agent
from rag.pipeline import RAGPipeline
from utils.helpers import create_screen_candidate
from utils.prometheus_metrics import SCREENING_DURATION, CANDIDATES_SCREENED
from utils.prompts import SCREENING_SYSTEM_PROMPT

logger = structlog.get_logger()


class ScreeningAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession, rag: RAGPipeline):
        self.llm = llm
        self.db = db
        self.rag = rag

    def _build_profile_text(self, profile: CandidateProfile) -> str:
        parts = []
        if profile.summary:
            parts.append(f"Summary: {profile.summary}")
        parts.append(f"Skills: {', '.join(profile.skills)}")
        parts.append(f"Experience: {profile.experience_years:.1f} years")
        if profile.location:
            parts.append(f"Location: {profile.location}")
        for emp in profile.employment_history[:5]:
            desc = f"  - {emp.title} at {emp.company} ({emp.start_date}-{emp.end_date or 'Present'})"
            if emp.description:
                desc += f": {emp.description[:200]}"
            parts.append(desc)
        for edu in profile.education[:3]:
            parts.append(f"  - {edu.degree} in {edu.field_of_study} at {edu.institution}")
        return "\n".join(parts)

    def _build_criteria(self, jd_parsed: JDParsed) -> List[Dict[str, Any]]:
        criteria = []
        for skill in jd_parsed.must_have_skills:
            criteria.append({"name": f"Must-have: {skill}", "weight": 2.0})
        for skill in jd_parsed.nice_to_have_skills[:5]:
            criteria.append({"name": f"Nice-to-have: {skill}", "weight": 1.0})
        criteria.append({"name": "Years of Experience", "weight": 1.5})
        criteria.append({"name": "Location Fit", "weight": 1.0})
        criteria.append({"name": "Seniority Match", "weight": 1.5})
        return criteria

    async def _screen_candidate(
        self,
        profile: CandidateProfile,
        jd_parsed: JDParsed,
        criteria: List[Dict],
        jd_id: str,
    ) -> ScreeningResult:
        user_prompt = create_screen_candidate(
            jd_parsed=jd_parsed, 
            criteria=criteria, 
            profile=self._build_profile_text(profile)
        )
        try:
            result = await self.llm.call_json(
                system_prompt=SCREENING_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name="screening_agent",
                jd_id=jd_id,
                use_flash=False,   # Use Pro for screening — quality matters
            )

            criterion_scores = []
            total_weighted, total_weight = 0.0, 0.0
            criterion_weights = {c["name"]: c["weight"] for c in criteria}

            for cs_dict in result.get("criterion_scores", []):
                weight = criterion_weights.get(cs_dict["criterion"], 1.0)
                cs = CriterionScore(
                    criterion=cs_dict["criterion"],
                    score=float(cs_dict["score"]),
                    reasoning=cs_dict["reasoning"],
                    evidence=cs_dict.get("evidence", ""),
                    weight=weight,
                )
                criterion_scores.append(cs)
                total_weighted += cs.score * weight
                total_weight += weight

            overall = total_weighted / total_weight if total_weight > 0 else 0.0

            return ScreeningResult(
                candidate_id=profile.candidate_id,
                jd_id=jd_id,
                criterion_scores=criterion_scores,
                overall_score=round(overall, 2),
                strengths=result.get("strengths", []),
                gaps=result.get("gaps", []),
                screening_summary=result.get("screening_summary", ""),
            )
        except Exception as exc:
            logger.error("screening_failed", candidate_id=profile.candidate_id, error=str(exc))
            # Return minimal screening result on failure
            return ScreeningResult(
                candidate_id=profile.candidate_id,
                jd_id=jd_id,
                criterion_scores=[],
                overall_score=0.0,
                strengths=[],
                gaps=["Screening failed — could not evaluate"],
                screening_summary="Automated screening encountered an error.",
            )

    @observe_agent("screening_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd_id = state.jd_id
        jd_parsed = state.jd_parsed
        profiles = state.deduplicated_profiles
        log = logger.bind(agent="screening", jd_id=jd_id)
        log.info("start", candidates=len(profiles))

        # ── RAG retrieval: narrow down to most relevant candidates ──
        rag_matches = await self.rag.retrieve(
            jd_title=jd_parsed.title if jd_parsed else "",
            jd_description=state.jd_raw.description,
            must_have_skills=jd_parsed.must_have_skills if jd_parsed else [],
            nice_to_have_skills=jd_parsed.nice_to_have_skills if jd_parsed else [],
            location=jd_parsed.location if jd_parsed else "",
            min_years=jd_parsed.years_experience.min if jd_parsed else 0,
            max_years=jd_parsed.years_experience.max if jd_parsed else 10,
            top_k=60,
        )

        # Build candidate text map for re-ranking
        profile_map = {p.candidate_id: p for p in profiles}
        candidate_texts = {
            p.candidate_id: self._build_profile_text(p)
            for p in profiles
        }

        # Re-rank
        if not jd_parsed:
            return state
        
        query = f"{jd_parsed.title} {' '.join(jd_parsed.must_have_skills)}"
        reranked = await self.rag.rerank(query, rag_matches, candidate_texts, top_k=30)

        # Build ordered screening list: reranked first, then remaining
        reranked_ids = [m.get("metadata", {}).get("candidate_id") for m, _ in reranked]
        top_profiles = [profile_map[cid] for cid in reranked_ids if cid in profile_map]

        # Add profiles not in RAG index (newly ingested)
        indexed_ids = set(reranked_ids)
        remaining = [p for p in profiles if p.candidate_id not in indexed_ids]
        candidates_to_screen = (top_profiles + remaining)[:40]  # screen top 40

        criteria = self._build_criteria(jd_parsed)
        log.info("screening_start", to_screen=len(candidates_to_screen))

        # ── Fan-Out: screen all candidates concurrently ──────────
        # Semaphore to avoid hammering the LLM API
        sem = asyncio.Semaphore(5)

        async def screen_with_semaphore(p):
            async with sem:
                return await self._screen_candidate(p, jd_parsed, criteria, jd_id)

        tasks = [screen_with_semaphore(p) for p in candidates_to_screen]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        screening_results = []
        for p, result in zip(candidates_to_screen, results):
            if isinstance(result, Exception):
                log.error("candidate_screen_failed", candidate_id=p.candidate_id, error=str(result))
            else:
                screening_results.append(result)
                # Update candidate status in DB
                p.status = CandidateStatus.SCREENED

        # Persist candidates to DB
        for profile in candidates_to_screen:
            sr = next((r for r in screening_results if r.candidate_id == profile.candidate_id), None)
            candidate_model = CandidateModel(
                candidate_id=profile.candidate_id,
                jd_id=jd_id,
                name=profile.name,
                email=profile.email,
                phone=profile.phone,
                location=profile.location,
                skills=profile.skills,
                experience_years=profile.experience_years,
                education=[e.model_dump() for e in profile.education],
                employment_history=[e.model_dump() for e in profile.employment_history],
                summary=profile.summary,
                source_profiles=[sp.model_dump() for sp in profile.source_profiles],
                linkedin_url=profile.linkedin_url,
                status=profile.status.value,
                screening_data=sr.model_dump() if sr else None,
                overall_score=sr.overall_score if sr else None,
            )
            self.db.add(candidate_model)

        SCREENING_DURATION.observe(time.monotonic())  # approximate — full elapsed via observe_agent
        CANDIDATES_SCREENED.labels(jd_id=jd_id).inc(len(screening_results))
        log.info("screening_complete", screened=len(screening_results))
        state.screening_results = screening_results
        state.step = "screened"
        return state
