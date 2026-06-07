"""
SQLAlchemy async ORM models for PostgreSQL.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, func
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship

from backend.utils.helpers import gen_uuid


class Base(AsyncAttrs, DeclarativeBase):
    pass


class JDModel(Base):
    __tablename__ = "job_descriptions"

    jd_id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    must_have_skills = Column(JSON, default=list)
    nice_to_have_skills = Column(JSON, default=list)
    years_exp_min = Column(Integer, default=0)
    years_exp_max = Column(Integer, default=10)
    location = Column(String(200))
    employment_type = Column(String(50))
    target_hiring_date = Column(String(20))
    status = Column(String(20), default="OPEN")
    parsed_data = Column(JSON, nullable=True)
    compliance_passed = Column(Boolean, nullable=True)
    compliance_flags = Column(JSON, default=list)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    created_by = Column(String(100), default="system")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    candidates = relationship("CandidateModel", back_populates="jd", cascade="all, delete-orphan")
    audit_records = relationship("AuditModel", back_populates="jd")
    conversations = relationship("ConversationModel", back_populates="jd", cascade="all, delete-orphan")


class CandidateModel(Base):
    __tablename__ = "candidates"

    candidate_id = Column(String, primary_key=True, default=gen_uuid)
    jd_id = Column(String, ForeignKey("job_descriptions.jd_id"), nullable=False)
    name = Column(String(200))
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(200), nullable=True)
    skills = Column(JSON, default=list)
    experience_years = Column(Float, default=0.0)
    education = Column(JSON, default=list)
    employment_history = Column(JSON, default=list)
    summary = Column(Text, nullable=True)
    source_profiles = Column(JSON, default=list)
    embedding_id = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    status = Column(String(30), default="SOURCED")
    screening_data = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    final_rank = Column(Integer, nullable=True)
    outreach_draft = Column(Text, nullable=True)
    # Human-in-the-loop: recruiter score overrides + notes
    recruiter_score_overrides = Column(JSON, nullable=True)   # {criterion: new_score}
    recruiter_weight_overrides = Column(JSON, nullable=True)  # {criterion: weight}
    recruiter_notes = Column(Text, nullable=True)
    outreach_sent_at = Column(DateTime, nullable=True)
    outreach_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    jd = relationship("JDModel", back_populates="candidates")
    feedback_records = relationship("RecruiterFeedbackModel", back_populates="candidate", cascade="all, delete-orphan")
    outreach_history = relationship("OutreachHistoryModel", back_populates="candidate", cascade="all, delete-orphan")


class AuditModel(Base):
    __tablename__ = "audit_logs"

    audit_id = Column(String, primary_key=True, default=gen_uuid)
    jd_id = Column(String, ForeignKey("job_descriptions.jd_id"))
    selected_candidate_id = Column(String, nullable=True)
    candidate_name = Column(String(200), nullable=True)
    recruiter_id = Column(String(100))
    action = Column(String(50))          # JD_CREATED, JD_CLOSED, CANDIDATE_REJECTED, SCORE_OVERRIDDEN, etc.
    reason = Column(Text, nullable=True)
    ranking_snapshot = Column(JSON, nullable=True)
    metadata = Column(JSON, default=dict)
    closed_at = Column(DateTime, default=func.now())
    jd = relationship("JDModel", back_populates="audit_records")


class TokenUsageModel(Base):
    """Tracks per-call LLM token usage for cost guardrails."""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jd_id = Column(String, nullable=True)
    agent_name = Column(String(100))
    model_name = Column(String(100))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    retries = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class RecruiterFeedbackModel(Base):
    """
    Stores recruiter score overrides and feedback per candidate.
    Used for HITL overrides and future feedback-based ranking improvement.
    """
    __tablename__ = "recruiter_feedback"

    feedback_id = Column(String, primary_key=True, default=gen_uuid)
    jd_id = Column(String, ForeignKey("job_descriptions.jd_id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"), nullable=False)
    recruiter_id = Column(String(100), nullable=False)
    # Score overrides: {"Python": 9.5, "FastAPI": 8.0}
    score_overrides = Column(JSON, default=dict)
    # Weight overrides: {"Python": 3.0, "Leadership": 0.5}
    weight_overrides = Column(JSON, default=dict)
    # Free-text notes
    notes = Column(Text, nullable=True)
    # Shortlist decision: APPROVE, REJECT, HOLD
    decision = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=func.now())
    candidate = relationship("CandidateModel", back_populates="feedback_records")


class ConversationModel(Base):
    """
    Persists recruiter conversation turns per JD.
    Enables multi-turn refinement (e.g. 'show me only remote candidates').
    """
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True, default=gen_uuid)
    jd_id = Column(String, ForeignKey("job_descriptions.jd_id"), nullable=False)
    recruiter_id = Column(String(100), nullable=False)
    role = Column(String(20))       # "user" | "assistant"
    content = Column(Text, nullable=False)
    metadata = Column(JSON, default=dict)   # tool_calls, token_usage, etc.
    created_at = Column(DateTime, default=func.now())
    jd = relationship("JDModel", back_populates="conversations")


class OutreachHistoryModel(Base):
    """
    Tracks every outreach message sent per candidate.
    Enables outreach history persistence as required by spec.
    """
    __tablename__ = "outreach_history"

    outreach_id = Column(String, primary_key=True, default=gen_uuid)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"), nullable=False)
    jd_id = Column(String, nullable=False)
    recruiter_id = Column(String(100))
    subject = Column(String(500))
    body = Column(Text)
    channel = Column(String(50), default="email")   # email | linkedin | sms
    sent_at = Column(DateTime, nullable=True)
    response_received = Column(Boolean, default=False)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    candidate = relationship("CandidateModel", back_populates="outreach_history")
