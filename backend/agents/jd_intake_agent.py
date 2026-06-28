"""
JD Intake Agent
Responsibilities:
  - Validate and parse incoming JD
  - Extract structured representation via LLM
  - Store JD in PostgreSQL
  - Return parsed JD + status
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_client import LLMClient
from core.schemas import JDParsed, JDStatus, WorkflowState
from db.models import AuditModel, JDModel
from observability.telemetry import observe_agent
from utils.prompts import JD_PARSE_SYSTEM_PROMPT
from utils.helpers import create_user_prompt
from utils.prometheus_metrics import JDS_CREATED

logger = structlog.get_logger()


class JDIntakeAgent:
    def __init__(self, llm: LLMClient, db: AsyncSession):
        self.llm = llm
        self.db = db
    
    def persist_to_db(self, jd_model: JDModel, audit_model: AuditModel):
        self.db.add(jd_model)
        self.db.add(audit_model)

    @observe_agent("jd_intake_agent")
    async def run(self, state: WorkflowState) -> WorkflowState:
        jd = state.jd_raw
        jd_id = state.jd_id
        log = logger.bind(agent="jd_intake", jd_id=jd_id)
        log.info("start")

        try:
            user_prompt = create_user_prompt(jd)
            parsed_dict = await self.llm.call_json(
                system_prompt=JD_PARSE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                agent_name="jd_intake_agent",
                jd_id=jd_id,
            )
            jd_parsed = JDParsed(**parsed_dict)
            jd_model = JDModel(
                jd_id=jd_id,
                title=jd_parsed.title,
                description=jd_parsed.description,
                must_have_skills=jd_parsed.must_have_skills,
                nice_to_have_skills=jd_parsed.nice_to_have_skills,
                years_exp_min=jd_parsed.years_experience.min,
                years_exp_max=jd_parsed.years_experience.max,
                location=jd_parsed.location,
                employment_type=jd_parsed.employment_type,
                target_hiring_date=str(jd_parsed.target_hiring_date),
                status=JDStatus.OPEN.value,
                parsed_data=parsed_dict,
                created_by="system",
            )
            audit_model = AuditModel(
                jd_id=jd_id,
                recruiter_id="system",
                action="JD_CREATED",
                metadata={"title": jd_parsed.title},
            )
            self.persist_to_db(jd_model=jd_model, audit_model=audit_model)
            await self.db.flush()

            JDS_CREATED.inc()
            log.info("success", seniority=jd_parsed.seniority_level)

            state.jd_parsed = jd_parsed
            state.step = "jd_parsed"
            return state

        except Exception as exc:
            log.error("failed", error=str(exc))
            state.error = f"JD Intake failed: {exc}"
            return state
