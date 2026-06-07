from typing import Any, List, Optional, Tuple

def get_skills(skills_raw: List) -> List:
    skills = []
    
    for s in skills_raw:
        if isinstance(s, dict):
            skills.append(s.get("name", ""))
            skills.extend((s.get("keywords") or [])[:5])
        elif isinstance(s, str):
            skills.append(s)
    
    return [sk.strip() for sk in skills if sk.strip()][:30]

def get_employment(work_details: List) -> Tuple[List, float]:
    employment = []
    total_years = 0.0
    
    for job in work_details[:10]:
        if not isinstance(job, dict):
            continue
        
        start_raw = str(job.get("startDate", "2020"))[:4]
        end_raw = job.get("endDate", "")
        end_yr = int(str(end_raw)[:4]) if end_raw and str(end_raw)[:4].isdigit() else 2024
        try:
            total_years += max(0, end_yr - int(start_raw))
        except Exception:
            pass
        employment.append({
            "company": job.get("company", job.get("name", "Unknown")),
            "title": job.get("position", ""),
            "start_date": job.get("startDate", ""),
            "end_date": job.get("endDate", "Present"),
            "description": (job.get("summary") or job.get("description") or "")[:500],
            "is_current": not bool(job.get("endDate")),
        })
    
    return employment, total_years

def get_education(edu_details: List) -> List:

    def _safe_year(val: Any) -> Optional[int]:
        try:
            return int(str(val)[:4]) if val else None
        except Exception:
            return None
    
    education = []
    
    for edu in edu_details[:5]:
        if not isinstance(edu, dict):
            continue
        education.append({
            "institution": edu.get("institution", ""),
            "degree": edu.get("studyType", ""),
            "field_of_study": edu.get("area", ""),
            "start_year": _safe_year(edu.get("startDate")),
            "end_year": _safe_year(edu.get("endDate")),
        })
    
    return education
        