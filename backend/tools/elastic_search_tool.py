"""
Elasticsearch integration for full-text profile search.

Used as a complementary search layer alongside Pinecone:
  - Pinecone: semantic/vector similarity
  - Elasticsearch: keyword + BM25 full-text search over raw profile text
  - Results from both are merged (union) before deduplication

Index: recruitment_profiles
  - Stores profile text, skills, location, experience for BM25 search
  - Updated on every batch ingest alongside Pinecone
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

from core.config import get_settings
from core.schemas import CandidateProfile
from observability.telemetry import record_tool_call
from utils.consts import INDEX_NAME, INDEX_MAPPING

logger = structlog.get_logger()
settings = get_settings()


class ElasticsearchClient:
    """Async Elasticsearch client for profile indexing and search."""

    def __init__(self):
        self._client: Optional[AsyncElasticsearch] = None

    def _get_client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(
                hosts=[settings.elasticsearch_url],
                request_timeout=10,
                retry_on_timeout=True,
                max_retries=3,
            )
        return self._client

    async def ensure_index(self) -> None:
        """Create index with mapping if it doesn't exist."""
        client = self._get_client()
        try:
            exists = await client.indices.exists(index=INDEX_NAME)
            if not exists:
                await client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
                logger.info("es_index_created", index=INDEX_NAME)
        except Exception as exc:
            logger.warning("es_index_create_failed", error=str(exc))

    def _build_doc(self, profile: CandidateProfile) -> Dict[str, Any]:
        """Convert CandidateProfile to ES document."""
        employment_text = " | ".join(
            f"{e.title} at {e.company}: {e.description or ''}"
            for e in profile.employment_history[:5]
        )
        education_text = " | ".join(
            f"{e.degree or ''} {e.field_of_study or ''} at {e.institution}"
            for e in profile.education[:3]
        )
        return {
            "candidate_id": profile.candidate_id,
            "name": profile.name,
            "email": profile.email or "",
            "location": profile.location or "",
            "skills": " ".join(profile.skills),
            "skills_keyword": profile.skills[:20],
            "experience_years": profile.experience_years,
            "summary": profile.summary or "",
            "employment_text": employment_text,
            "education_text": education_text,
            "sources": [sp.source for sp in profile.source_profiles],
        }

    async def index_profile(self, profile: CandidateProfile) -> None:
        """Index a single profile."""
        client = self._get_client()
        try:
            doc = self._build_doc(profile)
            await client.index(
                index=INDEX_NAME,
                id=profile.candidate_id,
                body=doc,
            )
        except Exception as exc:
            logger.warning("es_index_profile_failed", candidate_id=profile.candidate_id, error=str(exc))

    async def bulk_index(self, profiles: List[CandidateProfile]) -> None:
        """Bulk index a list of profiles."""
        if not profiles:
            return
        client = self._get_client()
        try:
            actions = [
                {
                    "_index": INDEX_NAME,
                    "_id": p.candidate_id,
                    "_source": self._build_doc(p),
                }
                for p in profiles
            ]
            await async_bulk(client, actions, raise_on_error=False)
            logger.info("es_bulk_indexed", count=len(profiles))
        except Exception as exc:
            logger.warning("es_bulk_index_failed", error=str(exc))
    
    def get_filters(
            self, 
            location: Optional[str] = None,
            min_years: Optional[float] = None,
            max_years: Optional[float] = None,
        ) -> List[Dict[str, Dict[str, Dict]]]:
        
        filters = []
        if min_years is not None:
            filters.append({"range": {"experience_years": {"gte": min_years}}})
        if max_years is not None:
            filters.append({"range": {"experience_years": {"lte": max_years}}})
        if location:
            filters.append({"match": {"location": {"query": location, "fuzziness": "AUTO"}}})
        
        return filters

    async def search(
        self,
        query_text: str,
        must_have_skills: List[str],
        location: Optional[str] = None,
        min_years: Optional[float] = None,
        max_years: Optional[float] = None,
        size: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid BM25 search with filters.
        Returns list of hits with candidate_id and score.
        """
        start = time.monotonic()
        client = self._get_client()

        es_query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query_text,
                            "fields": [
                                "summary^1.5",
                                "skills^2.0",
                                "employment_text^1.2",
                                "education_text",
                            ],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                        }
                    }
                ],
                "should": [
                    {"match": {"skills": {"query": skill, "boost": 2.0}}}
                    for skill in must_have_skills[:5]
                ],
                "filter": self.get_filters(location=location, min_years=min_years, max_years=max_years),
                "minimum_should_match": 0,
            }
        }

        try:
            response = await client.search(
                index=INDEX_NAME,
                body={"query": es_query, "size": size, "_source": ["candidate_id", "name", "skills", "location", "experience_years"]},
            )
            hits = response["hits"]["hits"]
            record_tool_call("es_search", time.monotonic() - start, success=True)
            logger.info("es_search", results=len(hits), query=query_text[:50])
            return [
                {
                    "candidate_id": h["_source"]["candidate_id"],
                    "es_score": h["_score"],
                    "name": h["_source"].get("name"),
                    "skills": h["_source"].get("skills_keyword", []),
                }
                for h in hits
            ]
        except NotFoundError:
            logger.warning("es_index_not_found", index=INDEX_NAME)
            return []
        except Exception as exc:
            record_tool_call("es_search", time.monotonic() - start, success=False)
            logger.error("es_search_failed", error=str(exc))
            return []

    async def close(self) -> None:
        if self._client:
            await self._client.close()


# Module-level singleton
_es_client: Optional[ElasticsearchClient] = None


def get_es_client() -> ElasticsearchClient:
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient()
    return _es_client
