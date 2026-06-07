"""
RAG Pipeline for candidate profiles.

Architecture:
  1. Ingest: embed resume text → upsert to Pinecone with metadata
  2. Retrieve: hybrid search (semantic vector + metadata filters)
  3. Re-rank: cross-encoder re-ranking of top-k results

Embedding strategy:
  Text = resume summary + skills joined + work history titles + education
  Metadata = skills list, experience_years, location, sources
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import CrossEncoder, SentenceTransformer

from backend.core.config import get_settings
from backend.core.schemas import CandidateProfile
from backend.observability.telemetry import record_tool_call
from backend.utils.consts import INDEX_DIMENSION, TOP_K_RERANK, TOP_K_RETRIEVE

settings = get_settings()
logger = structlog.get_logger()


class RAGPipeline:
    """
    Singleton-safe RAG pipeline.
    - Pinecone serverless for vector storage
    - SentenceTransformer for embeddings
    - CrossEncoder for re-ranking
    """

    def __init__(self):
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._embedder: Optional[SentenceTransformer] = None
        self._reranker: Optional[CrossEncoder] = None
        self._index = None

    def _get_embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder

    def _get_reranker(self) -> CrossEncoder:
        if self._reranker is None:
            self._reranker = CrossEncoder(settings.reranker_model)
        return self._reranker

    def _get_index(self):
        if self._index is None:
            existing = [idx.name for idx in self._pc.list_indexes()]
            if settings.pinecone_index_name not in existing:
                self._pc.create_index(
                    name=settings.pinecone_index_name,
                    dimension=INDEX_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                logger.info("pinecone_index_created", name=settings.pinecone_index_name)
            self._index = self._pc.Index(settings.pinecone_index_name)
        return self._index

    def _build_embedding_text(self, profile: CandidateProfile) -> str:
        """Construct rich text for embedding from candidate profile."""
        parts = []
        if profile.summary:
            parts.append(profile.summary)
        if profile.skills:
            parts.append("Skills: " + ", ".join(profile.skills))
        
        for emp in profile.employment_history[:5]:
            role = f"{emp.title} at {emp.company}"
            if emp.description:
                role += f": {emp.description[:200]}"
            parts.append(role)
        
        for edu in profile.education[:3]:
            edu_str = f"{edu.degree or ''} {edu.field_of_study or ''} at {edu.institution}".strip()
            parts.append(edu_str)
        
        if profile.location:
            parts.append(f"Location: {profile.location}")
        
        return " | ".join(filter(None, parts))

    def _build_metadata(self, profile: CandidateProfile) -> Dict[str, Any]:
        """Pinecone metadata for hybrid filtering."""
        return {
            "candidate_id": profile.candidate_id,
            "name": profile.name,
            "location": (profile.location or "").lower(),
            "experience_years": profile.experience_years,
            "skills": profile.skills[:20],      # Pinecone metadata list limit
            "sources": [sp.source for sp in profile.source_profiles],
            "email": profile.email or "",
        }

    async def ingest_profile(self, profile: CandidateProfile) -> str:
        """Embed and upsert a single profile. Returns embedding_id."""
        start = time.monotonic()
        try:
            text = self._build_embedding_text(profile)
            embedder = self._get_embedder()
            vector = embedder.encode(text).tolist()

            index = self._get_index()
            embedding_id = f"candidate_{profile.candidate_id}"
            index.upsert(vectors=[{
                "id": embedding_id,
                "values": vector,
                "metadata": self._build_metadata(profile),
            }])

            record_tool_call("rag_ingest", time.monotonic() - start)
            return embedding_id

        except Exception as exc:
            record_tool_call("rag_ingest", time.monotonic() - start, success=False)
            logger.error("rag_ingest_error", candidate_id=profile.candidate_id, error=str(exc))
            raise

    async def ingest_batch(self, profiles: List[CandidateProfile], batch_size: int = 50) -> None:
        """Batch upsert profiles to Pinecone."""
        embedder = self._get_embedder()
        index = self._get_index()

        for i in range(0, len(profiles), batch_size):
            batch = profiles[i:i + batch_size]
            texts = [self._build_embedding_text(p) for p in batch]
            vectors = embedder.encode(texts, batch_size=32, show_progress_bar=True).tolist()

            upsert_data = [
                {
                    "id": f"candidate_{p.candidate_id}",
                    "values": v,
                    "metadata": self._build_metadata(p),
                }
                for p, v in zip(batch, vectors)
            ]
            index.upsert(vectors=upsert_data)
            logger.info("rag_batch_upsert", count=len(batch), offset=i)

    def _build_filter(
        self,
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build Pinecone metadata filter dict."""
        filters: Dict[str, Any] = {}
        if location:
            filters["location"] = {"$eq": location.lower()}
        if min_years is not None and max_years is not None:
            filters["experience_years"] = {"$gte": min_years, "$lte": max_years}
        elif min_years is not None:
            filters["experience_years"] = {"$gte": min_years}
        # Note: Pinecone doesn't support $all for lists in serverless; use $in for any-match
        # Skills are post-filtered in Python for exact must-have matching
        return filters if filters else {}

    def _build_query_text(
        self,
        must_have_skills: List[str],
        nice_to_have_skills: List[str],
        title: str,
        description: str,
    ) -> str:
        """Build JD text for similarity search."""
        parts = [
            f"Job Title: {title}",
            f"Required Skills: {', '.join(must_have_skills)}",
        ]
        if nice_to_have_skills:
            parts.append(f"Nice to have: {', '.join(nice_to_have_skills)}")
        if description:
            parts.append(description[:500])
        return " | ".join(parts)

    async def retrieve(
        self,
        jd_title: str,
        jd_description: str,
        must_have_skills: List[str],
        nice_to_have_skills: List[str],
        location: Optional[str] = None,
        min_years: Optional[int] = None,
        max_years: Optional[int] = None,
        top_k: int = TOP_K_RETRIEVE,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval: semantic search + metadata filters.
        Returns raw Pinecone matches with metadata.
        """
        start = time.monotonic()
        try:
            query_text = self._build_query_text(
                must_have_skills, nice_to_have_skills, jd_title, jd_description
            )
            embedder = self._get_embedder()
            query_vector = embedder.encode(query_text).tolist()

            pinecone_filter = self._build_filter(location, min_years, max_years)

            index = self._get_index()
            kwargs: Dict[str, Any] = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": True,
            }
            if pinecone_filter:
                kwargs["filter"] = pinecone_filter

            results = index.query(**kwargs)
            matches = results.get("matches", [])
            record_tool_call("rag_retrieve", time.monotonic() - start)
            logger.info("rag_retrieve", query=jd_title, matches=len(matches))
            return matches

        except Exception as exc:
            record_tool_call("rag_retrieve", time.monotonic() - start, success=False)
            logger.error("rag_retrieve_error", error=str(exc))
            return []

    async def rerank(
        self,
        query: str,
        matches: List[Dict[str, Any]],
        candidate_texts: Dict[str, str],  # candidate_id → profile text
        top_k: int = TOP_K_RERANK,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Cross-encoder re-ranking of initial retrieval results.
        Returns (match, rerank_score) sorted descending.
        """
        if not matches:
            return []

        reranker = self._get_reranker()
        pairs = []
        valid_matches = []

        for match in matches:
            cid = match.get("metadata", {}).get("candidate_id", "")
            profile_text = candidate_texts.get(cid, "")
            if profile_text:
                pairs.append([query, profile_text[:512]])
                valid_matches.append(match)

        if not pairs:
            return [(m, m.get("score", 0.0)) for m in matches[:top_k]]

        scores = reranker.predict(pairs)
        ranked = sorted(zip(valid_matches, scores.tolist()), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# Module-level singleton
_rag: Optional[RAGPipeline] = None


def get_rag() -> RAGPipeline:
    global _rag
    if _rag is None:
        _rag = RAGPipeline()
    return _rag
