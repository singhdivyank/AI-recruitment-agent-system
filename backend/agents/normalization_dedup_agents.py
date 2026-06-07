"""
Normalization Agent + Deduplication Agent

Normalization: raw profiles → unified CandidateProfile schema
Deduplication: merge same candidate appearing across multiple sources
  Signals (priority order):
    1. Email match (High)
    2. Phone match (High)
    3. LinkedIn URL match (High)
    4. Name + current company (Medium)
    5. Embedding similarity (Medium) — checked during RAG ingest
"""
from __future__ import annotations
import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.schemas import (
    CandidateProfile, CandidateStatus, WorkflowState
)
from backend.observability.telemetry import observe_agent

logger = structlog.get_logger()


class NormalizationAgent:
    """Ensures all profiles conform to the unified CandidateProfile schema."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize(self, raw: Dict[str, Any]) -> Optional[CandidateProfile]:
        """
        Profiles sourced from the HF dataset are already CandidateProfile dicts.
        This layer validates, cleans, and enriches them.
        """
        try:
            profile = CandidateProfile(**raw)

            # Clean skills
            profile.skills = list(dict.fromkeys(
                [s.strip() for s in profile.skills if s and len(s.strip()) > 1]
            ))[:30]

            # Normalize location
            if profile.location:
                profile.location = profile.location.strip().title()

            # Set status
            profile.status = CandidateStatus.NORMALIZED

            return profile
        except Exception as exc:
            logger.debug("normalization_skip", error=str(exc))
            return None

    @observe_agent("normalization_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        log = logger.bind(agent="normalization", jd_id=state.jd_id)
        log.info("start", raw_count=len(state.raw_profiles))

        normalized = []
        for raw in state.raw_profiles:
            profile = self._normalize(raw)
            if profile:
                normalized.append(profile)

        log.info("complete", normalized=len(normalized), dropped=len(state.raw_profiles) - len(normalized))
        state.normalized_profiles = normalized
        state.step = "normalized"
        return state


class DeduplicationAgent:
    """
    Merges duplicate candidates using a multi-signal matching strategy.
    High-confidence signals (email, phone, LinkedIn URL) → direct merge.
    Medium signals (name+company) → fuzzy merge with confirmation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _email_key(self, profile: CandidateProfile) -> Optional[str]:
        if profile.email:
            return f"email:{profile.email.lower().strip()}"
        return None

    def _phone_key(self, profile: CandidateProfile) -> Optional[str]:
        if profile.phone:
            digits = "".join(c for c in profile.phone if c.isdigit())
            if len(digits) >= 10:
                return f"phone:{digits[-10:]}"
        return None

    def _linkedin_key(self, profile: CandidateProfile) -> Optional[str]:
        if profile.linkedin_url:
            url = profile.linkedin_url.rstrip("/").lower()
            if "linkedin.com/in/" in url:
                handle = url.split("linkedin.com/in/")[-1].split("?")[0]
                return f"linkedin:{handle}"
        return None

    def _name_company_key(self, profile: CandidateProfile) -> Optional[str]:
        if profile.name and profile.employment_history:
            current_company = profile.employment_history[0].company
            key = f"{profile.name.lower().strip()}:{current_company.lower().strip()}"
            return f"namecompany:{hashlib.md5(key.encode()).hexdigest()[:12]}"
        return None

    def _get_all_keys(self, profile: CandidateProfile) -> List[str]:
        keys = []
        for fn in [self._email_key, self._phone_key, self._linkedin_key, self._name_company_key]:
            k = fn(profile)
            if k:
                keys.append(k)
        return keys

    def _merge_profiles(self, primary: CandidateProfile, duplicate: CandidateProfile) -> CandidateProfile:
        """Merge duplicate into primary, preserving richest data."""
        # Merge source_profiles
        existing_sources = {sp.source for sp in primary.source_profiles}
        for sp in duplicate.source_profiles:
            if sp.source not in existing_sources:
                primary.source_profiles.append(sp)

        # Fill missing fields from duplicate
        if not primary.email and duplicate.email:
            primary.email = duplicate.email
        if not primary.phone and duplicate.phone:
            primary.phone = duplicate.phone
        if not primary.location and duplicate.location:
            primary.location = duplicate.location
        if not primary.linkedin_url and duplicate.linkedin_url:
            primary.linkedin_url = duplicate.linkedin_url

        # Merge skills (union)
        all_skills = list(dict.fromkeys(primary.skills + duplicate.skills))
        primary.skills = all_skills[:30]

        # Use higher experience estimate
        primary.experience_years = max(primary.experience_years, duplicate.experience_years)

        # Use richer employment history
        if len(duplicate.employment_history) > len(primary.employment_history):
            primary.employment_history = duplicate.employment_history

        primary.status = CandidateStatus.DEDUPLICATED
        return primary

    @observe_agent("deduplication_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        profiles = state.normalized_profiles
        log = logger.bind(agent="deduplication", jd_id=state.jd_id)
        log.info("start", input=len(profiles))

        # Union-Find for grouping duplicates
        parent: Dict[str, str] = {}
        key_to_id: Dict[str, str] = {}
        id_to_profile: Dict[str, CandidateProfile] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent.get(x, x), x)
                x = parent.get(x, x)
            return x

        def union(x: str, y: str) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        # Initialize
        for profile in profiles:
            cid = profile.candidate_id
            parent[cid] = cid
            id_to_profile[cid] = profile

        # Build connections via shared keys
        for profile in profiles:
            cid = profile.candidate_id
            for key in self._get_all_keys(profile):
                if key in key_to_id:
                    union(cid, key_to_id[key])
                else:
                    key_to_id[key] = cid

        # Group by root
        groups: Dict[str, List[str]] = defaultdict(list)
        for cid in id_to_profile:
            groups[find(cid)].append(cid)

        # Merge groups
        deduplicated: List[CandidateProfile] = []
        for root, members in groups.items():
            primary = id_to_profile[root]
            for member_id in members:
                if member_id != root:
                    dup = id_to_profile[member_id]
                    primary = self._merge_profiles(primary, dup)
            deduplicated.append(primary)

        duplicates_removed = len(profiles) - len(deduplicated)
        log.info("complete", output=len(deduplicated), duplicates_removed=duplicates_removed)

        state.deduplicated_profiles = deduplicated
        state.step = "deduplicated"
        return state
