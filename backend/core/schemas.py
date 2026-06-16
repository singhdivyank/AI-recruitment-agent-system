"""
Unified Pydantic schemas for the entire recruitment system.
These are the canonical data contracts used across all agents and APIs.
"""
from __future__ import annotations
import uuid
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────

class JDStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    SOURCING = "SOURCING"
    SCREENING = "SCREENING"
    SHORTLISTED = "SHORTLISTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"

class EmploymentType(str, Enum):
    FULL_TIME = "Full-Time"
    PART_TIME = "Part-Time"
    CONTRACT = "Contract"
    FREELANCE = "Freelance"
    INTERNSHIP = "Internship"

class CandidateStatus(str, Enum):
    SOURCED = "SOURCED"
    NORMALIZED = "NORMALIZED"
    DEDUPLICATED = "DEDUPLICATED"
    SCREENED = "SCREENED"
    SHORTLISTED = "SHORTLISTED"
    OUTREACH_SENT = "OUTREACH_SENT"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"

class SourcePlatform(str, Enum):
    LINKEDIN = "LinkedIn"
    NAUKRI = "Naukri"
    ATS = "ATS"


# ─── JD Schemas ───────────────────────────────────────────────

class YearsExperience(BaseModel):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @field_validator("max")
    @classmethod
    def max_gte_min(cls, v: int, info) -> int:
        if "min" in info.data and v < info.data["min"]:
            raise ValueError("max must be >= min")
        return v


class JDCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=50)
    must_have_skills: List[str] = Field(min_length=1)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    years_experience: YearsExperience
    location: str
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    target_hiring_date: date
    department: Optional[str] = None
    salary_range: Optional[str] = None


class JDParsed(BaseModel):
    """Structured output from the JD Intake Agent after LLM parsing."""
    title: str
    seniority_level: str          # Junior / Mid / Senior / Lead / Principal
    must_have_skills: List[str]
    nice_to_have_skills: List[str]
    years_experience: YearsExperience
    location: str
    employment_type: str
    remote_ok: bool
    hiring_urgency: str           # low / medium / high
    key_responsibilities: List[str]
    ideal_candidate_summary: str
    description: str
    target_hiring_date: date


class JDResponse(BaseModel):
    jd_id: str
    title: str
    description: str
    must_have_skills: List[str]
    nice_to_have_skills: List[str]
    years_experience: YearsExperience
    location: str
    employment_type: str
    target_hiring_date: date
    status: JDStatus
    parsed: Optional[JDParsed] = None
    compliance_passed: Optional[bool] = None
    compliance_flags: List[str] = Field(default_factory=list)
    total_candidates: int = 0
    shortlisted_count: int = 0
    token_usage: int = 0
    estimated_cost_usd: float = 0.0
    created_at: datetime
    updated_at: datetime
    created_by: str

    model_config = {"from_attributes": True}


# ─── Candidate / Profile Schemas ──────────────────────────────

class SourceProfile(BaseModel):
    source: SourcePlatform
    url: Optional[str] = None
    raw_id: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class EducationEntry(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class EmploymentEntry(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    is_current: bool = False


class CandidateProfile(BaseModel):
    """Unified candidate schema — the single record after normalization."""
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience_years: float = 0.0
    education: List[EducationEntry] = Field(default_factory=list)
    employment_history: List[EmploymentEntry] = Field(default_factory=list)
    summary: Optional[str] = None
    source_profiles: List[SourceProfile] = Field(default_factory=list)
    embedding_id: Optional[str] = None
    status: CandidateStatus = CandidateStatus.SOURCED
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


# ─── Screening Schemas ────────────────────────────────────────

class CriterionScore(BaseModel):
    criterion: str
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    evidence: Optional[str] = None     # exact text from profile supporting the score
    weight: float = 1.0                # set by ranking agent


class ScreeningResult(BaseModel):
    candidate_id: str
    jd_id: str
    criterion_scores: List[CriterionScore]
    overall_score: float = Field(ge=0.0, le=10.0)
    strengths: List[str]
    gaps: List[str]
    screening_summary: str
    screened_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Ranking Schemas ──────────────────────────────────────────

class RankedCandidate(BaseModel):
    rank: int
    candidate: CandidateProfile
    screening: ScreeningResult
    final_score: float
    score_breakdown: Dict[str, float]
    rationale: str
    outreach_draft: Optional[str] = None


class ShortlistResponse(BaseModel):
    jd_id: str
    shortlist: List[RankedCandidate]
    top_pick: Optional[RankedCandidate]
    top_pick_justification: str
    total_candidates_evaluated: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Closure Schemas ──────────────────────────────────────────

class JDCloseRequest(BaseModel):
    jd_id: str
    selected_candidate_id: str
    recruiter_id: str
    notes: Optional[str] = None


class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    jd_id: str
    selected_candidate_id: str
    candidate_name: str
    recruiter_id: str
    reason: str
    ranking_snapshot: Dict[str, Any]
    closed_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Workflow State ───────────────────────────────────────────

class WorkflowState(BaseModel):
    """LangGraph state object passed between all agent nodes."""
    jd_id: str
    jd_raw: JDCreate
    jd_parsed: Optional[JDParsed] = None
    jd_response: Optional[JDResponse] = None
    compliance_passed: bool = False
    compliance_flags: List[str] = Field(default_factory=list)
    raw_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    normalized_profiles: List[CandidateProfile] = Field(default_factory=list)
    deduplicated_profiles: List[CandidateProfile] = Field(default_factory=list)
    screening_results: List[ScreeningResult] = Field(default_factory=list)
    shortlist: Optional[ShortlistResponse] = None
    outreach_drafts: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None
    step: str = "init"
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    messages: List[Dict[str, str]] = Field(default_factory=list)


class ScoreOverrideRequest(BaseModel):
    recruiter_id: str
    score_overrides: Dict[str, float]       # {"Python": 9.5, "FastAPI": 8.0}
    weight_overrides: Dict[str, float] = {}  # {"Python": 3.0}
    notes: Optional[str] = None
    decision: Optional[str] = None               # APPROVE | REJECT | HOLD

# ── Conversation / Refinement Endpoints ───────────────────────

class ConversationMessage(BaseModel):
    recruiter_id: str
    content: str

# ── Outreach History Endpoints ────────────────────────────────

class OutreachSendRequest(BaseModel):
    recruiter_id: str
    subject: str
    body: str
    channel: str = "email"