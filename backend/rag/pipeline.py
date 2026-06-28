"""
RAG Pipeline — pgvector implementation
=======================================
Drop-in replacement for the Pinecone pipeline.
Same public interface: ingest_profile(), ingest_batch(), retrieve(), rerank()
Everything runs inside the existing PostgreSQL container — no external services.

Storage:
  Table: profile_embeddings
  Column: embedding vector(384)   ← pgvector
  Index:  IVFFlat (cosine)        ← approximate nearest neighbour

Retrieval:
  1. Metadata pre-filter  (SQL WHERE clauses on location, experience_years)
  2. Semantic search      (pgvector <=> cosine distance operator)
  3. CrossEncoder rerank  (ms-marco-MiniLM-L-6-v2)

Why pgvector over Pinecone for this project:
  - Runs inside the existing Docker postgres container
  - No external API key or account required
  - Full SQL expressiveness for metadata filters (LIKE, ranges, arrays)
  - Atomic with the rest of the DB (same transaction boundary)
  - Starter-plan Pinecone restricts to AWS only; pgvector has no such limits
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .query_defs import (
    CREATE_INDEX, 
    CREATE_TABLE, 
    EMBEDDING_INGESTION, 
    EMBEDDING_INGESTION_BATCHES,
    RETRIEVAL
)
from core.config import get_settings
from core.schemas import CandidateProfile
from observability.telemetry import record_tool_call
from utils.consts import (
    INDEX_DIMENSION, 
    IVFFLAT_LISTS, 
    TOP_K_RETRIEVE, 
    TOP_K_RERANK
)

logger = structlog.get_logger()
settings = get_settings()


async def _embed(texts: List[str]) -> List[List[float]]:
    """Call inference service /embed. Returns one 384-dim vector per text."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{settings.inference_service_url}/embed",
            json={"texts": texts, "batch_size": 32},
        )
        resp.raise_for_status()
        return resp.json()["vectors"]


async def _rerank(query: str, passages: List[str]) -> List[float]:
    """Call inference service /rerank. Returns one score per (query, passage) pair."""
    pairs = [{"query": query, "passage": p[:512]} for p in passages]
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{settings.inference_service_url}/rerank",
            json={"pairs": pairs},
        )
        resp.raise_for_status()
        return resp.json()["scores"]

class RAGPipeline:
    def __init__(self):
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def ensure_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(CREATE_TABLE.format({"dimensions": INDEX_DIMENSION})))
            result = await conn.execute(text("SELECT COUNT(*) FROM profile_embeddings"))
            row_count = result.scalar() or 0
            if row_count >= IVFFLAT_LISTS:
                await conn.execute(text(CREATE_INDEX))
        logger.info("pgvector_schema_ready")

    def _build_profile_text(self, profile: CandidateProfile) -> str:
        parts = []
        if profile.skills:
            parts.append("Skills: " + ", ".join(profile.skills))
            parts.append(" ".join(profile.skills[:10]))
        if profile.summary:
            parts.append(profile.summary)
        for emp in profile.employment_history[:5]:
            role = f"{emp.title} at {emp.company}"
            if emp.description:
                role += f": {emp.description[:200]}"
            parts.append(role)
        for edu in profile.education[:3]:
            edu_str = f"{edu.degree or ''} {edu.field_of_study or ''} at {edu.institution}".strip()
            if edu_str:
                parts.append(edu_str)
        if profile.location:
            parts.append(f"Location: {profile.location}")
        return " | ".join(filter(None, parts))

    def _build_query_text(
        self,
        jd_title: str,
        must_have_skills: List[str],
        nice_to_have_skills: List[str],
        description: str,
    ) -> str:
        parts = [
            f"Job Title: {jd_title}",
            f"Required Skills: {', '.join(must_have_skills)}",
        ]
        if nice_to_have_skills:
            parts.append(f"Nice to have: {', '.join(nice_to_have_skills)}")
        if description:
            parts.append(description[:400])
        return " | ".join(parts)

    async def ingest_profile(self, profile: CandidateProfile) -> str:
        start = time.monotonic()
        try:
            profile_text = self._build_profile_text(profile)
            vectors = await _embed([profile_text])
            vector_str = f"[{','.join(str(v) for v in vectors[0])}]"

            async with self._session_factory() as session:
                await session.execute(text(EMBEDDING_INGESTION), {
                    "cid":          profile.candidate_id,
                    "name":         profile.name,
                    "email":        profile.email or "",
                    "location":     (profile.location or "").lower(),
                    "exp":          profile.experience_years,
                    "skills":       profile.skills[:30],
                    "sources":      [sp.source for sp in profile.source_profiles],
                    "profile_text": profile_text[:2000],
                    "embedding":    vector_str,
                })
                await session.commit()

            record_tool_call("pgvector_ingest", time.monotonic() - start)
            return profile.candidate_id

        except Exception as exc:
            record_tool_call("pgvector_ingest", time.monotonic() - start, success=False)
            logger.error("pgvector_ingest_error", candidate_id=profile.candidate_id, error=str(exc))
            raise

    async def ingest_batch(self, profiles: List[CandidateProfile], batch_size: int = 50) -> None:
        if not profiles:
            return

        for i in range(0, len(profiles), batch_size):
            batch = profiles[i:i + batch_size]
            texts = [self._build_profile_text(p) for p in batch]

            # Single HTTP call to inference service for the whole batch
            vectors = await _embed(texts)

            async with self._session_factory() as session:
                for profile, vector in zip(batch, vectors):
                    vector_str = f"[{','.join(str(v) for v in vector)}]"
                    await session.execute(text(EMBEDDING_INGESTION_BATCHES), {
                        "cid":          profile.candidate_id,
                        "name":         profile.name,
                        "email":        profile.email or "",
                        "location":     (profile.location or "").lower(),
                        "exp":          profile.experience_years,
                        "skills":       profile.skills[:30],
                        "sources":      [sp.source for sp in profile.source_profiles],
                        "profile_text": texts[batch.index(profile)][:2000],
                        "embedding":    vector_str,
                    })
                await session.commit()

            logger.info("pgvector_batch_upsert", count=len(batch), offset=i)

        await self._maybe_rebuild_index()

    async def _maybe_rebuild_index(self) -> None:
        async with self._engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM profile_embeddings"))
            count = result.scalar() or 0
            if count >= IVFFLAT_LISTS:
                await conn.execute(text(CREATE_INDEX))

    async def retrieve(
        self,
        jd_title: str,
        jd_description: str,
        must_have_skills: List[str],
        nice_to_have_skills: List[str],
        top_k: int = TOP_K_RETRIEVE,
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        start = time.monotonic()
        try:
            query_text = self._build_query_text(
                jd_title, must_have_skills, nice_to_have_skills, jd_description
            )
            # Single HTTP call to inference service
            vectors = await _embed([query_text])
            query_vector_str = f"[{','.join(str(v) for v in vectors[0])}]"

            filters = []
            params: Dict[str, Any] = {"query_vector": query_vector_str, "top_k": top_k}

            if location:
                filters.append("location ILIKE :location")
                params["location"] = f"%{location.lower()}%"
            if min_years is not None:
                filters.append("experience_years >= :min_years")
                params["min_years"] = float(min_years)
            if max_years is not None:
                filters.append("experience_years <= :max_years")
                params["max_years"] = float(max_years)

            where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

            async with self._session_factory() as session:
                result = await session.execute(text(RETRIEVAL.format(
                    {"where_clause": where_clause, "top_k": top_k}
                )), params)
                rows = result.fetchall()

            matches = [
                {
                    "candidate_id":     row.candidate_id,
                    "name":             row.name,
                    "location":         row.location,
                    "experience_years": row.experience_years,
                    "skills":           row.skills or [],
                    "sources":          row.sources or [],
                    "profile_text":     row.profile_text,
                    "score":            float(row.similarity_score),
                    "metadata": {
                        "candidate_id":     row.candidate_id,
                        "name":             row.name,
                        "location":         row.location,
                        "experience_years": row.experience_years,
                        "skills":           row.skills or [],
                    },
                }
                for row in rows
            ]

            record_tool_call("pgvector_retrieve", time.monotonic() - start)
            logger.info("pgvector_retrieve", query=jd_title, matches=len(matches))
            return matches

        except Exception as exc:
            record_tool_call("pgvector_retrieve", time.monotonic() - start, success=False)
            logger.error("pgvector_retrieve_error", error=str(exc))
            return []

    async def rerank(
        self,
        query: str,
        matches: List[Dict[str, Any]],
        candidate_texts: Dict[str, str],
        top_k: int = TOP_K_RERANK,
    ) -> List[Tuple[Dict[str, Any], float]]:
        if not matches:
            return []

        passages = []
        valid_matches = []
        for match in matches:
            cid = match.get("candidate_id") or match.get("metadata", {}).get("candidate_id", "")
            profile_text = candidate_texts.get(cid) or match.get("profile_text", "")
            if profile_text:
                passages.append(profile_text)
                valid_matches.append(match)

        if not passages:
            return [(m, m.get("score", 0.0)) for m in matches[:top_k]]

        # Single HTTP call to inference service
        scores = await _rerank(query, passages)

        ranked = sorted(
            zip(valid_matches, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

_rag: Optional[RAGPipeline] = None


def get_rag() -> RAGPipeline:
    global _rag
    if _rag is None:
        _rag = RAGPipeline()
    return _rag
