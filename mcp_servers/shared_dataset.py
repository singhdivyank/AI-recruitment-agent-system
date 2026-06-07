"""
Shared dataset loader for all three MCP servers.
Loads the HuggingFace json_resume_dataset once and partitions it:
  LinkedIn : rows   0% - 40%   (+ 20-row overlap with Naukri for dedup testing)
  Naukri   : rows  38% - 70%   (starts 20 rows before 40% boundary)
  ATS      : rows  70% - 100%
"""
from __future__ import annotations
import hashlib
import random
from typing import Any, Dict, List, Optional

from .helpers import get_skills, get_employment, get_education

# Module-level cache
_all_profiles: Optional[List[Dict]] = None


def _load_all() -> List[Dict]:
    global _all_profiles
    if _all_profiles is not None:
        return _all_profiles
    try:
        from datasets import load_dataset
        ds = load_dataset("InferenceEndpoint/json_resume_dataset", split="train")
        _all_profiles = list(ds)
        print(f"[dataset] Loaded {len(_all_profiles)} profiles from HuggingFace")
    except Exception as exc:
        print(f"[dataset] HF load failed ({exc}), using synthetic fallback")
        _all_profiles = _synthetic(500)
    return _all_profiles


def get_partition(source: str) -> List[Dict]:
    """Return the dataset partition for a given source name."""
    all_data = _load_all()
    n = len(all_data)
    if source == "linkedin":
        return all_data[0:int(n * 0.40)]
    elif source == "naukri":
        # Starts 20 rows before the 40% boundary → deliberate overlap
        start = max(0, int(n * 0.40) - 20)
        return all_data[start:int(n * 0.70)]
    elif source == "ats":
        return all_data[int(n * 0.70):]
    return all_data


def normalize(raw: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    """Convert a JSON Resume dict to the canonical CandidateProfile dict."""
    try:
        basics = raw["basics"]
        name = basics["name"]
        if not name:
            return None

        email, phone, loc = basics["email"], basics["phone"], basics["location"]
        
        location: Optional[str] = ", ".join(filter(None, [loc.get("city", ""), loc.get("countryCode", "")]))
        linkedin_url: str = ""

        # Skills
        skills_raw = raw["skills"]
        skills = get_skills(skills_raw)
        # Employment
        work_raw = raw["work"]
        employment, total_years = get_employment(work_raw)
        # Education
        education_raw = raw["education"]
        education = get_education(education_raw)

        for p in (basics["profiles"]):
            if isinstance(p, dict) and "linkedin" in p["network"].lower():
                linkedin_url = p["url"]

        candidate_id = hashlib.md5((email or name).encode()).hexdigest()[:16]

        return {
            "candidate_id": candidate_id,
            "name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "skills": skills,
            "experience_years": min(total_years, 40.0),
            "education": education,
            "employment_history": employment,
            "summary": basics.get("summary", ""),
            "linkedin_url": linkedin_url,
            "source": source,
            "source_profiles": [{"source": source.capitalize(), "raw_id": candidate_id, "url": linkedin_url}],
        }
    except Exception as exc:
        return None


def filter_profiles(
    partition: List[Dict],
    source: str,
    skills: List[str],
    min_years: int,
    page: int,
    page_size: int,
) -> List[Dict]:
    """Normalize, filter, paginate."""
    must_lower = [s.lower() for s in skills]
    results = []
    for raw in partition:
        p = normalize(raw, source)
        if not p:
            continue
        if p["experience_years"] < min_years:
            continue
        if must_lower:
            profile_skills_lower = [sk.lower() for sk in p["skills"]]
            if not any(any(req in sk for sk in profile_skills_lower) for req in must_lower):
                continue
        results.append(p)
    random.shuffle(results)
    return results[page * page_size:(page + 1) * page_size]

def _synthetic(count: int) -> List[Dict]:
    from faker import Faker
    fake = Faker()
    tech_skills = [
        "Python", "FastAPI", "LangChain", "RAG", "PostgreSQL", "Redis",
        "Docker", "Kubernetes", "React", "TypeScript", "LLMs", "NLP",
        "Machine Learning", "TensorFlow", "PyTorch", "SQL", "AWS", "GCP",
        "Pinecone", "LangGraph",
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
            "skills": [{"name": s, "keywords": random.sample(tech_skills, 2)} for s in random.sample(tech_skills, random.randint(3, 8))],
            "work": [{
                "company": fake.company(),
                "position": random.choice(["Software Engineer", "Senior Engineer", "AI Engineer"]),
                "startDate": f"{random.randint(2016, 2021)}-01",
                "endDate": f"{random.randint(2022, 2024)}-12",
                "summary": fake.paragraph(nb_sentences=2),
            } for _ in range(random.randint(1, 4))],
            "education": [{"institution": fake.company() + " University", "studyType": "B.S.", "area": "Computer Science", "startDate": "2012-09", "endDate": "2016-05"}],
        })
    return profiles
