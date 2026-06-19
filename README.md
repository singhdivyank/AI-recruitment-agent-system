# AI Recruitment Agent

A production-grade multi-agent recruitment automation system. Accepts a Job Description, sources candidates from simulated LinkedIn/Naukri/ATS feeds (backed by the HuggingFace `json_resume_dataset`), screens them with per-criterion LLM reasoning, ranks them using a weighted scoring formula, drafts outreach messages, and generates a full audit trail — all with a single API call.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd recruitment-agent

# 2. Set up environment
cp .env.example .env
# Edit .env and fill in:
#   GOOGLE_API_KEY     (Google AI Studio key for Gemini 2.5 Pro)
#   PINECONE_API_KEY   (Pinecone serverless)
#   LANGCHAIN_API_KEY  (LangSmith — optional but recommended)

# 3. Launch everything
docker compose up --build
```

**That's it.** After ~2 minutes for image builds:

| Service            | URL                                 |
| ------------------ | ----------------------------------- |
| Recruiter UI       | http://localhost:3000               |
| API Docs (Swagger) | http://localhost:8000/docs          |
| Grafana Dashboards | http://localhost:3001 (admin/admin) |
| Prometheus         | http://localhost:9090               |

---

## Prerequisites

- Docker + Docker Compose v2
- A Google AI Studio API key (free at https://aistudio.google.com)
- A Pinecone account (free tier works — create an index named `recruitment-profiles` with dimension 384)
- A LangSmith account (optional — traces disabled if key not set)

---

## Architecture Overview

```
Next.js UI → FastAPI → LangGraph Workflow
                             │
             ┌───────────────┼──────────────────┐
             ▼               ▼                  ▼
        JD Intake      Compliance         Sourcing (fan-out)
             │               │              │    │    │
             └───────────────┘         LinkedIn Naukri ATS
                                            │
                                     Normalization → Dedup
                                            │
                                     RAG Ingest (Pinecone)
                                            │
                                     RAG Retrieve + Rerank
                                            │
                                     Screening (parallel, top-40)
                                            │
                                     Ranking → Outreach Drafts
                                            │
                                     Recruiter Approval
                                            │
                                     Closure + Audit Log
```

**Full topology:** See [`docs/architecture.md`](docs/architecture.md)
**Design decisions:** See [`docs/decisions.md`](docs/decisions.md)

---

## Agent Pipeline

| #   | Agent             | Model                  | Purpose                                                   |
| --- | ----------------- | ---------------------- | --------------------------------------------------------- |
| 1   | **JD Intake**     | Gemini 2.5 Pro         | Parse JD → structured schema (seniority, skills, urgency) |
| 2   | **Compliance**    | Gemini Flash           | Detect discriminatory language (regex + LLM)              |
| 3   | **Sourcing**      | —                      | Fan-out to LinkedIn/Naukri/ATS (asyncio.gather)           |
| 4   | **Normalization** | —                      | Unify all profiles to CandidateProfile schema             |
| 5   | **Deduplication** | —                      | Union-Find merge of cross-source duplicates               |
| 6   | **RAG Ingest**    | all-MiniLM-L6-v2       | Embed + upsert profiles to Pinecone                       |
| 7   | **Screening**     | Gemini 2.5 Pro         | Per-criterion scoring with evidence (semaphore=5)         |
| 8   | **Ranking**       | Gemini 2.5 Pro + Flash | Weighted score + rationale + top-pick selection           |
| 9   | **Outreach**      | Gemini Flash           | Personalized outreach emails (parallel, semaphore=3)      |
| 10  | **Closure**       | Gemini Flash           | Audit trail + JD close + database finalization            |

---

## API Reference

### Submit a Job Description

```bash
curl -X POST http://localhost:8000/api/v1/jds \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior AI Engineer",
    "description": "We are building next-gen LLM-powered products...",
    "must_have_skills": ["Python", "LangChain", "RAG", "FastAPI"],
    "nice_to_have_skills": ["Kubernetes", "Pinecone", "LangGraph"],
    "years_experience": {"min": 4, "max": 10},
    "location": "San Francisco, CA",
    "employment_type": "Full-Time",
    "target_hiring_date": "2025-09-01"
  }'
```

Response: `{"jd_id": "...", "status": "PROCESSING"}`

### Poll JD Status

```bash
curl http://localhost:8000/api/v1/jds/{jd_id}
```

### Get Shortlist

```bash
curl http://localhost:8000/api/v1/jds/{jd_id}/shortlist
```

### Close JD (select candidate)

```bash
curl -X POST http://localhost:8000/api/v1/jds/{jd_id}/close \
  -H "Content-Type: application/json" \
  -d '{
    "jd_id": "{jd_id}",
    "selected_candidate_id": "{candidate_id}",
    "recruiter_id": "recruiter-1",
    "notes": "Best technical fit, available immediately"
  }'
```

### Get Audit Log

```bash
curl http://localhost:8000/api/v1/jds/{jd_id}/audit
```

### Get Daily Cost

```bash
curl http://localhost:8000/api/v1/metrics/cost
```

---

## Cost Guardrails

Configured via `.env`:

| Variable              | Default | Description                            |
| --------------------- | ------- | -------------------------------------- |
| `MAX_TOKENS_PER_JD`   | 500,000 | Token cap per JD lifecycle             |
| `MAX_COST_PER_JD_USD` | $5.00   | Dollar cap per JD                      |
| `DAILY_BUDGET_USD`    | $100.00 | Daily spend ceiling                    |
| `MAX_LLM_RETRIES`     | 3       | Retries per call (exponential backoff) |

A `CostGuardrailError` aborts the pipeline immediately if limits would be exceeded. Retries always send the **original prompt only** — never append prior context — to prevent token explosion.

---

## Observability

### LangSmith (LLM Tracing)

Every LLM call is traced with full prompt, response, token counts, and latency.
Set `LANGCHAIN_API_KEY` and `LANGCHAIN_TRACING_V2=true` in `.env`.
View at: https://smith.langchain.com

### Prometheus Metrics (http://localhost:9090)

Key metrics:

```
recruitment_agent_calls_total{agent_name, status}
recruitment_llm_calls_total{agent_name, model, status}
recruitment_llm_tokens_total{agent_name, model, token_type}
recruitment_llm_cost_usd_total{agent_name, model}
recruitment_llm_latency_seconds{agent_name, model}
recruitment_candidates_sourced_total{source}
recruitment_jds_created_total
recruitment_jds_closed_total
recruitment_active_workflows
recruitment_daily_cost_usd
```

### Grafana (http://localhost:3001)

Login: `admin` / configured via `GRAFANA_PASSWORD` env var.
Datasource auto-provisioned from Prometheus.

### OpenTelemetry

Distributed traces exported via gRPC to the OTel Collector (port 4317).
Traces include the full workflow span with per-agent child spans.

---

## Project Structure

```
recruitment-agent/
├── backend/
│   ├── agents/               # All 10 specialist agents
│   │   ├── jd_intake_agent.py
│   │   ├── compliance_agent.py
│   │   ├── sourcing_agent.py
│   │   ├── normalization_dedup_agents.py
│   │   ├── screening_agent.py
│   │   ├── ranking_agent.py
│   │   └── outreach_closure_agents.py
│   ├── api/
│   │   └── evaluation.py
│   ├── core/
│   │   ├── config.py         # Pydantic settings
│   │   ├── llm_client.py     # Gemini client + cost guardrails
│   │   └── schemas.py        # All Pydantic models
│   ├── db/
│   │   ├── models.py         # SQLAlchemy async models
│   │   └── session.py        # Async session factory
│   ├── observability/
│   │   └── telemetry.py      # Prometheus + OTel + structlog
│   ├── rag/
│   │   └── pipeline.py       # Pinecone + CrossEncoder RAG
│   ├── tools/
│   │   ├── elastic_search_tool.py
│   │   ├── mcp_client.py
│   │   ├── sourcing_tools.py # HF dataset + 3 source simulators
│   │   └── tool_registry.py
│   ├── utils/
│   │   ├── consts.py
│   │   ├── helpers.py
│   │   ├── prometheus_metrics.py
│   │   └── prompts.py
│   ├── workflows/
│   │   ├── orchestrator.py   # LangGraph StateGraph
│   │   └── workflow_utils.py
│   ├── Dockerfile
│   ├── main.py               # FastAPI app + all routes
│   └── requirements.txt
│
├── frontend/
│   ├──public/
│   │   └── .gitkeep
│   ├──src/
│   │   ├── app/
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx     # Root layout with Sidebar shell
│   │   │   ├── page.tsx       # Dashboard (KPIs + AgentDAG + JD table)
│   │   │   ├── candidates/
│   │   │   │   └── page.tsx
│   │   │   ├── evaluation/
│   │   │   │   └── page.tsx
│   │   │   ├── integrations/
│   │   │   │   └── page.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── observability/
│   │   │   │   └── page.tsx
│   │   │   ├── settings/
│   │   │   │   └── page.tsx
│   │   │   └── workflows/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── candidates/
│   │   │   │   └── CandidateCard.tsx
│   │   │   ├── dashboard/
│   │   │   │   └── AgentWorkflowDAG.tsx # Signature hero element
│   │   │   ├── jobs/
│   │   │   │   └── JDFormModal.tsx
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Topbar.tsx
│   │   │   └── ui/
│   │   │       ├── KpiCard.tsx
│   │   │       ├── PipelineTrack.tsx
│   │   │       ├── ScoreBar.tsx
│   │   │       └── StatusBadge.tsx
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── index.ts
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── next-env.d.ts
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── inference_service/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── schemas.py
│
├── mcp_servers/
│   ├── ats/
│   │    └── server.py
│   ├── linkedin/
│   │    └── server.py
│   ├── naukri/
│   │    └── server.py
│   ├── Dockerfile
│   ├── helpers.py
│   ├── requirements.txt
│   └── shared_dataset.py
│
├── monitoring/
│   ├── grafana/
│   │    ├── dashboards/
│   │    │    ├── dashboards.yml
│   │    │    └── recruitment_dashboard.json
│   │    └── datasources.yml
│   ├── prometheus/
│   │    └── prometheus.yml
│   └── otel-config.yml
│
├── docs/
│   ├── architecture.md       # Full system design + diagrams
│   └── decisions.md          # Key design decisions + rationale
│
├── scripts/
│   └── init_db.sql
├── .env.example
├── .gitignore
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

## Development

### Run backend locally (without Docker)

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in keys
uvicorn main:app --reload --port 8000
```

### Run frontend locally

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Run only infrastructure (DB + Redis + monitoring)

```bash
docker compose up postgres redis prometheus grafana otel-collector
```

---

## Environment Variables Reference

See `.env.example` for the full list. Minimum required to run:

```bash
GOOGLE_API_KEY=...        # Gemini 2.5 Pro access
LANGCHAIN_API_KEY=...     # LangSmith LLM tracing
HF_TOKEN=...              # If dataset requires auth
POSTGRES_PASSWORD=...
```
