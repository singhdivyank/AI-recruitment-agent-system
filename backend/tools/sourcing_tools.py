"""
Resume dataset loader and multi-source simulator.

Uses `json_resume_dataset` from HuggingFace (JSON Resume schema).
Splits the dataset into three virtual "sources": LinkedIn, Naukri, ATS
to simulate realistic multi-source recruitment.
"""
from __future__ import annotations
import asyncio
import hashlib
import random
import time
from typing import Any, Dict, List, Optional

import structlog
from datasets import load_dataset

from backend.core.schemas import (
    CandidateProfile, SourcePlatform, SourceProfile
)
from backend.observability.telemetry import record_tool_call
from backend.utils.helpers import get_skills, get_employment_history, get_education_details
from backend.utils.prometheus_metrics import CANDIDATES_SOURCED

logger = structlog.get_logger()


class ResumeDatasetLoader:
    """Loads JSON Resume dataset and provides source-partitioned access."""

    _dataset: Optional[List[Dict]] = None

    @classmethod
    def _load(cls) -> List[Dict]:
        if cls._dataset is None:
            logger.info("loading_hf_dataset", dataset="json_resume_dataset")
            try:
                ds = load_dataset("InferenceEndpoint/json_resume_dataset", split="train")
                cls._dataset = [row for row in ds]
                logger.info("dataset_loaded", count=len(cls._dataset))
            except Exception as exc:
                logger.warning("hf_dataset_load_failed", error=str(exc))
                cls._dataset = _generate_synthetic_profiles(500)
        return cls._dataset

    @classmethod
    def get_source_partition(cls, source: SourcePlatform) -> List[Dict]:
        source_splits = {
            SourcePlatform.LINKEDIN: (0, 0.40),
            SourcePlatform.NAUKRI: (0.40, 0.70),
            SourcePlatform.ATS: (0.70, 1.00),
        }
        
        all_data = cls._load()
        n = len(all_data)
        start_pct, end_pct = source_splits[source]
        start_idx = int(n * start_pct)
        end_idx = int(n * end_pct)
        # Small overlap to test deduplication
        if source == SourcePlatform.NAUKRI:
            start_idx = max(0, start_idx - 20)
        return all_data[start_idx:end_idx]


def _normalize_json_resume(raw: Dict[str, Any], source: SourcePlatform) -> Optional[CandidateProfile]:
    """Convert JSON Resume schema to our CandidateProfile schema."""
    try:
        basics = raw.get("basics", {})
        name = basics.get("name", "Unknown")
        if not name or name == "Unknown":
            return None

        linkedin_url = ""
        total_years = 0.0
        
        email, phone, location_obj, summary = basics["email"], basics["phone"], \
            basics["location"], basics["summary"]

        city = location_obj["city"]
        country = location_obj["countryCode"]
        location = ", ".join(filter(None, [city, country])) or None

        for profile in (basics["profiles"]):
            if isinstance(profile, dict) and "linkedin" in (profile["network"]).lower():
                linkedin_url = profile["url"]
        
        skills_raw, work = raw["skills"], raw["work"]
        skills=get_skills(skills_raw=skills_raw)
        employment_history = get_employment_history(work=work)

        # Education
        education_raw = raw["education"]
        education=get_education_details(education_raw=education_raw)

        # Generate stable candidate_id from email or name
        id_seed = email or name
        candidate_id = hashlib.md5(id_seed.encode()).hexdigest()[:16]

        return CandidateProfile(
            candidate_id=candidate_id,
            name=name,
            email=email,
            phone=phone,
            location=location,
            skills=skills,
            experience_years=min(total_years, 40),
            education=education,
            employment_history=employment_history,
            summary=summary,
            linkedin_url=linkedin_url,
            source_profiles=[SourceProfile(
                source=source,
                url=linkedin_url if source == SourcePlatform.LINKEDIN else None,
                raw_id=candidate_id,
            )],
        )
    except Exception as exc:
        logger.debug("profile_parse_error", error=str(exc))
        return None


# ─── Source Search Tools ──────────────────────────────────────

async def search_linkedin(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Simulate LinkedIn search over the dataset partition."""
    start = time.monotonic()
    await asyncio.sleep(0.3)  # simulate network latency

    try:
        partition = ResumeDatasetLoader.get_source_partition(SourcePlatform.LINKEDIN)
        profiles = _filter_and_normalize(partition, SourcePlatform.LINKEDIN, must_have_skills, min_years)
        paginated = profiles[page * page_size:(page + 1) * page_size]
        CANDIDATES_SOURCED.labels(source="linkedin").inc(len(paginated))
        record_tool_call("search_linkedin", time.monotonic() - start)
        logger.info("linkedin_search", results=len(paginated), page=page)
        return paginated
    except Exception as exc:
        record_tool_call("search_linkedin", time.monotonic() - start, success=False)
        logger.error("linkedin_search_error", error=str(exc))
        return []


async def search_naukri(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Simulate Naukri search over the dataset partition."""
    start = time.monotonic()
    await asyncio.sleep(0.4)

    try:
        partition = ResumeDatasetLoader.get_source_partition(SourcePlatform.NAUKRI)
        profiles = _filter_and_normalize(partition, SourcePlatform.NAUKRI, must_have_skills, min_years)
        paginated = profiles[page * page_size:(page + 1) * page_size]
        CANDIDATES_SOURCED.labels(source="naukri").inc(len(paginated))
        record_tool_call("search_naukri", time.monotonic() - start)
        logger.info("naukri_search", results=len(paginated), page=page)
        return paginated
    except Exception as exc:
        record_tool_call("search_naukri", time.monotonic() - start, success=False)
        logger.error("naukri_search_error", error=str(exc))
        return []


async def search_ats(
    must_have_skills: List[str],
    min_years: int = 0,
    page: int = 0,
    page_size: int = 50,
) -> List[CandidateProfile]:
    """Simulate internal ATS search."""
    start = time.monotonic()
    await asyncio.sleep(0.1)

    try:
        partition = ResumeDatasetLoader.get_source_partition(SourcePlatform.ATS)
        profiles = _filter_and_normalize(partition, SourcePlatform.ATS, must_have_skills, min_years)
        paginated = profiles[page * page_size:(page + 1) * page_size]
        CANDIDATES_SOURCED.labels(source="ats").inc(len(paginated))
        record_tool_call("search_ats", time.monotonic() - start)
        logger.info("ats_search", results=len(paginated), page=page)
        return paginated
    except Exception as exc:
        record_tool_call("search_ats", time.monotonic() - start, success=False)
        logger.error("ats_search_error", error=str(exc))
        return []


def _filter_and_normalize(
    partition: List[Dict],
    source: SourcePlatform,
    must_have_skills: List[str],
    min_years: int,
) -> List[CandidateProfile]:
    """Normalize raw profiles and apply basic pre-filters."""
    results = []
    must_lower = [s.lower() for s in must_have_skills]

    for raw in partition:
        profile = _normalize_json_resume(raw, source)
        if not profile:
            continue

        # Experience filter
        if profile.experience_years < min_years:
            continue

        # Skill relevance: at least 1 must-have skill present (loose pre-filter)
        profile_skills_lower = [sk.lower() for sk in profile.skills]
        if must_lower and not any(
            any(req in sk for sk in profile_skills_lower) for req in must_lower
        ):
            continue

        results.append(profile)

    random.shuffle(results)  # simulate non-deterministic ordering from real APIs
    return results


def _generate_synthetic_profiles(count: int) -> List[Dict]:
    """Fallback: generate synthetic profiles if HF dataset unavailable."""
    from faker import Faker
    fake = Faker()
    tech_skills = [
        "Python", "FastAPI", "LangChain", "RAG", "PostgreSQL", "Redis",
        "Docker", "Kubernetes", "React", "TypeScript", "LLMs", "NLP",
        "Machine Learning", "TensorFlow", "PyTorch", "SQL", "AWS", "GCP",
        "Kafka", "Elasticsearch", "Pinecone", "LangGraph", "OpenAI API",
    ]
    profiles = []
    for _ in range(count):
        profiles.append({
            "basics": {
                "name": fake.name(),
                "email": fake.email(),
                "phone": fake.phone_number(),
                "location": {"city": fake.city(), "countryCode": "US"},
                "summary": fake.paragraph(nb_sentences=3),
                "profiles": [{"network": "LinkedIn", "url": f"https://linkedin.com/in/{fake.user_name()}"}],
            },
            "skills": [
                {"name": s, "keywords": random.sample(tech_skills, 3)}
                for s in random.sample(tech_skills, random.randint(3, 8))
            ],
            "work": [
                {
                    "company": fake.company(),
                    "position": random.choice(["Software Engineer", "Senior Engineer", "AI Engineer", "ML Engineer"]),
                    "startDate": f"{random.randint(2016, 2021)}-01",
                    "endDate": f"{random.randint(2022, 2024)}-12",
                    "summary": fake.paragraph(nb_sentences=2),
                }
                for _ in range(random.randint(1, 4))
            ],
            "education": [
                {
                    "institution": fake.company() + " University",
                    "studyType": random.choice(["B.S.", "M.S.", "Ph.D."]),
                    "area": random.choice(["Computer Science", "AI", "Data Science"]),
                    "startDate": "2012-09",
                    "endDate": "2016-05",
                }
            ],
        })
    return profiles
