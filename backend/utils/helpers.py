import math
import uuid
from typing import Any, Optional, List, Tuple

from backend.core.schemas import EmploymentEntry, EducationEntry
from backend.db.models import (
    AuditModel, 
    CandidateModel, 
    JDModel,
)

def gen_uuid() -> str:
    return str(uuid.uuid4())

def create_user_prompt(jd: Any) -> str:
    return f"""
        Job Title: {jd.title}
        Description: {jd.description}
        Must-Have Skills: {', '.join(jd.must_have_skills)}
        Nice-to-Have Skills: {', '.join(jd.nice_to_have_skills)}
        Years of Experience: {jd.years_experience.min}-{jd.years_experience.max}
        Location: {jd.location}
        Employment Type: {jd.employment_type}
        Target Hiring Date: {jd.target_hiring_date}
    """

def create_outreach_user_prompt(jd_parsed: Any, candidate: Any) -> str:
    return f"""
        Role: {jd_parsed.title} ({jd_parsed.seniority_level})
        Required Skills: {', '.join(jd_parsed.must_have_skills[:5])}
        Location: {jd_parsed.location} | Type: {jd_parsed.employment_type}

        Candidate: {candidate.name}
        Their Skills: {', '.join(candidate.skills[:10])}
        Experience: {candidate.experience_years:.0f} years
        Recent Role: {candidate.employment_history[0].title if candidate.employment_history else 'Not specified'} at {candidate.employment_history[0].company if candidate.employment_history else 'Unknown'}
    """

def create_justification_prompt(snapshot: dict, req: Any) -> str:
    return f"""
        Selected candidate: {snapshot.get('name')}
        Score: {snapshot.get('final_score')}/10
        Skills: {', '.join(snapshot.get('skills', [])[:8])}
        Experience: {snapshot.get('experience_years')} years
        Recruiter notes: {req.notes or 'None'}
    """

def create_rationale_prompt(jd_parsed: Any, candidate: Any, screening: Any) -> str:
    scores_text = "\n".join([
        f"  {cs.criterion}: {cs.score}/10 — {cs.reasoning}"
        for cs in screening.criterion_scores[:8]
    ])
    
    return f"""
        JD: {jd_parsed.title} | Seniority: {jd_parsed.seniority_level}
        Candidate: {candidate.name} | {candidate.experience_years:.1f} YOE | {candidate.location}
        Overall Score: {screening.overall_score}/10

        Criterion Scores:
        {scores_text}

        Strengths: {', '.join(screening.strengths[:3])}
        Gaps: {', '.join(screening.gaps[:3])}
    """

def create_top_pick_prompt(jd_parsed: Any, shortlist_text: str) -> str:
    return f"""
        JD: {jd_parsed.title}
        Required: {', '.join(jd_parsed.must_have_skills)}
        Seniority: {jd_parsed.seniority_level} | YOE: {jd_parsed.years_experience.min}-{jd_parsed.years_experience.max}

        Top Candidates:
        {shortlist_text}
    """

def get_skills(skills_raw: List) -> List:
    skills = []
    for s in skills_raw:
        if isinstance(s, dict):
            skills.append(s.get("name", ""))
            keywords = s.get("keywords") or []
            skills.extend(keywords[:5])
        elif isinstance(s, str):
            skills.append(s)
    skills = [sk for sk in skills if sk][:30]
    return skills

def get_employment_history(work: List) -> List:
    employment_history = []

    for job in work[:10]:
        if not isinstance(job, dict):
            continue

        entry = EmploymentEntry(
            company=job.get("company", job.get("name", "Unknown")),
            title=job.get("position", ""),
            start_date=job.get("startDate", ""),
            end_date=job.get("endDate", "Present"),
            description=job.get("summary", job.get("description", ""))[:500],
            is_current=not bool(job.get("endDate")),
        )
        employment_history.append(entry)
        # Rough YOE calculation
        try:
            start_yr = int(str(job.get("startDate", "2020"))[:4])
            end_yr_raw = job.get("endDate", "")
            end_yr = int(str(end_yr_raw)[:4]) if end_yr_raw and str(end_yr_raw)[:4].isdigit() else 2024
            total_years += max(0, end_yr - start_yr)
        except Exception:
            pass
    
    return employment_history

def get_education_details(education_raw: List) -> List:
    
    def _safe_year(val: Any) -> Optional[int]:
        try:
            return int(str(val)[:4]) if val else None
        except Exception:
            return None
    
    education = []
    
    for edu in education_raw[:5]:
        if not isinstance(edu, dict):
            continue
        education.append(EducationEntry(
            institution=edu.get("institution", ""),
            degree=edu.get("studyType", ""),
            field_of_study=edu.get("area", ""),
            start_year=_safe_year(edu.get("startDate")),
            end_year=_safe_year(edu.get("endDate")),
        ))
    
    return education

def _jd_to_dict(j: JDModel) -> dict:
    return {
        "jd_id": j.jd_id,
        "title": j.title,
        "description": j.description,
        "must_have_skills": j.must_have_skills,
        "nice_to_have_skills": j.nice_to_have_skills,
        "years_experience": {"min": j.years_exp_min, "max": j.years_exp_max},
        "location": j.location,
        "employment_type": j.employment_type,
        "target_hiring_date": j.target_hiring_date,
        "status": j.status,
        "parsed_data": j.parsed_data,
        "compliance_passed": j.compliance_passed,
        "compliance_flags": j.compliance_flags,
        "token_usage": (j.total_input_tokens or 0) + (j.total_output_tokens or 0),
        "estimated_cost_usd": j.estimated_cost_usd,
        "created_by": j.created_by,
        "created_at": str(j.created_at),
        "updated_at": str(j.updated_at),
    }


def _candidate_to_dict(c: CandidateModel) -> dict:
    return {
        "candidate_id": c.candidate_id,
        "jd_id": c.jd_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "location": c.location,
        "skills": c.skills,
        "experience_years": c.experience_years,
        "education": c.education,
        "employment_history": c.employment_history,
        "summary": c.summary,
        "source_profiles": c.source_profiles,
        "linkedin_url": c.linkedin_url,
        "status": c.status,
        "screening_data": c.screening_data,
        "overall_score": c.overall_score,
        "final_rank": c.final_rank,
        "outreach_draft": c.outreach_draft,
        "created_at": str(c.created_at),
    }


def _audit_to_dict(a: AuditModel) -> dict:
    return {
        "audit_id": a.audit_id,
        "jd_id": a.jd_id,
        "action": a.action,
        "selected_candidate_id": a.selected_candidate_id,
        "candidate_name": a.candidate_name,
        "recruiter_id": a.recruiter_id,
        "reason": a.reason,
        "closed_at": str(a.closed_at),
    }

def _dcg(relevances: List[float]) -> float:
    """Compute DCG for a ranked list of relevance scores."""
    return sum(
        rel / math.log2(rank + 2)
        for rank, rel in enumerate(relevances)
    )


def _ndcg_at_k(ranked_scores: List[float], k: int) -> float:
    """NDCG@k given a list of relevance scores in rank order."""
    ranked_k = ranked_scores[:k]
    ideal = sorted(ranked_scores, reverse=True)[:k]
    dcg = _dcg(ranked_k)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def _precision_at_k(ranked_scores: List[float], k: int, threshold: float = 6.0) -> float:
    """Precision@k: fraction of top-k that are 'relevant' (score >= threshold)."""
    top_k = ranked_scores[:k]
    relevant = sum(1 for s in top_k if s >= threshold)
    return relevant / k if k > 0 else 0.0


def _recall_at_k(ranked_scores: List[float], k: int, threshold: float = 6.0) -> float:
    """Recall@k: fraction of all relevant items in top-k."""
    total_relevant = sum(1 for s in ranked_scores if s >= threshold)
    if total_relevant == 0:
        return 0.0
    top_k_relevant = sum(1 for s in ranked_scores[:k] if s >= threshold)
    return top_k_relevant / total_relevant

def _comp_ai_score(candidate: Any, fb: Any) -> Tuple[List, List]:
    agreements, errors = [], []
    
    ai_scores = {
        cs["criterion"]: cs["score"]
        for cs in (candidate.screening_data.get("criterion_scores") or [])
    }
    for criterion, recruiter_score in (fb.score_overrides or {}).items():
        ai_score = ai_scores.get(criterion)
        if ai_score is not None:
            error = abs(float(ai_score) - float(recruiter_score))
            errors.append(error)
            agreements.append(1 if error <= 1.5 else 0)
    
    return agreements, errors