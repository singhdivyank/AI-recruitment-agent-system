# Architecture — AI Recruitment Agent

## Agent Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RECRUITER UI (Next.js)                      │
│                    Submit JD  |  View Pipeline  |  Approve          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ POST /api/v1/jds
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                       │
│         Auth (JWT) | CORS | Prometheus /metrics | OTel              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ BackgroundTask → OrchestratorAgent
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LangGraph StateGraph (OrchestratorAgent)           │
│                                                                     │
│   ┌──────────────┐    ┌──────────────┐                              │
│   │  JD Intake   │───▶│  Compliance  │                              │
│   │   Agent      │    │    Agent     │                              │
│   └──────────────┘    └──────┬───────┘                             │
│                              │ pass / fail                          │
│                         ┌────▼─────┐                               │
│                         │ Sourcing │ (fan-out below)                │
│                         │  Agent   │                               │
│                         └────┬─────┘                               │
│                              │                                      │
│          ┌───────────────────┼───────────────────┐                 │
│          ▼                   ▼                   ▼                  │
│    ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│    │ LinkedIn │       │  Naukri  │       │   ATS    │              │
│    │  Search  │       │  Search  │       │  Search  │              │
│    └──────────┘       └──────────┘       └──────────┘              │
│          │                   │                   │                  │
│          └───────────────────┼───────────────────┘                 │
│                              │ (fan-in)                             │
│                         ┌────▼──────────┐                          │
│                         │ Normalization │                           │
│                         │    Agent      │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │ Deduplication │                           │
│                         │    Agent      │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │  RAG Ingest   │  ←── Pinecone Vector DB  │
│                         │   (batch)     │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │  RAG Retrieve │  hybrid search + rerank  │
│                         │   + Re-rank   │                           │
│                         └────┬──────────┘                          │
│                              │ top-40 candidates                    │
│                              │                                      │
│     ┌───────────────────────┬┴──────────────────────────┐          │
│     ▼           ▼           ▼           ▼           ▼   ▼          │
│ ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐         │
│ │Screen │   │Screen │   │Screen │   │Screen │   │Screen │  ...    │
│ │  C1   │   │  C2   │   │  C3   │   │  C4   │   │  C5   │         │
│ └───────┘   └───────┘   └───────┘   └───────┘   └───────┘         │
│                              │ (fan-in)                             │
│                         ┌────▼──────────┐                          │
│                         │   Ranking     │                           │
│                         │    Agent      │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│          ┌───────────────────┼───────────────────┐                 │
│          ▼                   ▼                   ▼                  │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│   │Outreach  │       │Outreach  │       │Outreach  │              │
│   │Draft C1  │       │Draft C2  │       │Draft C3  │  ...         │
│   └──────────┘       └──────────┘       └──────────┘              │
│                              │ (fan-in)                             │
│                         ┌────▼──────────┐                          │
│                         │   Recruiter   │                           │
│                         │   Approval    │  ← human-in-the-loop     │
│                         └────┬──────────┘                          │
│                              │ confirm                              │
│                         ┌────▼──────────┐                          │
│                         │   Closure     │                           │
│                         │    Agent      │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                    ┌─────────▼──────────┐                          │
│                    │  Audit Log + DB    │                           │
│                    └────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Sequence Diagram

```
Recruiter          FastAPI          Orchestrator     Agents            External
   │                  │                  │              │                 │
   │─POST /jds───────▶│                  │              │                 │
   │◀─202 jd_id───────│                  │              │                 │
   │                  │──background──────▶│              │                 │
   │                  │                  │──JDIntake───▶│                 │
   │                  │                  │◀─parsed──────│                 │
   │                  │                  │──Compliance─▶│                 │
   │                  │                  │◀─pass/fail───│                 │
   │                  │                  │──Sourcing────▶│                │
   │                  │                  │              │──gather()──────▶│ LinkedIn
   │                  │                  │              │──gather()──────▶│ Naukri
   │                  │                  │              │──gather()──────▶│ ATS
   │                  │                  │              │◀───────profiles─│
   │                  │                  │◀─all profiles│                 │
   │                  │                  │──Normalize──▶│                 │
   │                  │                  │──Deduplicate▶│                 │
   │                  │                  │──RAG ingest─▶│──upsert────────▶│ Pinecone
   │                  │                  │──Screening──▶│──retrieve──────▶│ Pinecone
   │                  │                  │              │──rerank locally  │
   │                  │                  │              │──gather(screen)  │ Gemini
   │                  │                  │◀─scores──────│                 │
   │                  │                  │──Ranking────▶│                 │
   │                  │                  │──Outreach───▶│                 │
   │                  │                  │◀─shortlist───│                 │
   │──GET /shortlist─▶│                  │              │                 │
   │◀─ranked list─────│                  │              │                 │
   │──POST /close────▶│                  │              │                 │
   │                  │──ClosureAgent───▶│──audit log──▶│                 │
   │◀─closed──────────│                  │              │                 │
```

## Retrieval Flow

```
JD Text + Skills
       │
       ▼
SentenceTransformer(all-MiniLM-L6-v2) → 384-dim vector
       │
       ├── Semantic Search  ──────────────────────▶ Pinecone
       │                                              (cosine similarity)
       └── Metadata Filters ──────────────────────▶ Pinecone
           • location == jd.location                 (pre-filter)
           • experience_years >= min_years
           │
           ▼
        Top-50 matches
           │
           ▼
    CrossEncoder(ms-marco-MiniLM-L-6-v2)
    Re-scores each (query, profile_text) pair
           │
           ▼
        Top-20 re-ranked candidates → Screening Agent
```

## Tool Calling Flow

```
Agent calls tool → tool executes → result returned → state updated

Tools used per agent:
  SourcingAgent:     search_linkedin, search_naukri, search_ats
  ScreeningAgent:    rag_retrieve, score_candidate (via LLM)
  OutreachAgent:     draft_outreach (via LLM)
  ClosureAgent:      update_jd_state, close_jd (DB updates)

All tools:
  • Handle pagination (page, page_size params)
  • Return [] on empty results (no exception)
  • Wrap in try/except, log on failure, return fallback
  • Record latency to Prometheus
```

## State Transitions (JD lifecycle)

```
DRAFT ──submit──▶ OPEN
  OPEN ──intake──▶ SOURCING
  SOURCING ──sourced──▶ SCREENING
  SCREENING ──ranked──▶ SHORTLISTED
  SHORTLISTED ──recruiter confirms──▶ CLOSED
  Any ──compliance fail──▶ REJECTED
```

## Retry Strategy

```
LLM calls:
  max_retries = 3
  backoff = exponential (1s, 2s, 4s)
  CRITICAL: each retry sends ORIGINAL prompt only (not full history)
  → prevents $4K→$40K token explosion from retry storms

Tool calls:
  max_retries = 2 per source
  failed source does not block pipeline (return_exceptions=True)
  empty result = normal, not error

Cost guardrails (checked BEFORE every LLM call):
  per_jd_token_cap = 500,000 tokens
  per_jd_cost_cap = $5.00
  daily_budget_cap = $100.00
  → CostGuardrailError raised, never retried
```

## Observability Flow

```
Every agent call:
  → structlog JSON log (timestamp, agent, jd_id, latency, status)
  → OTel span (trace_id propagated through entire workflow)
  → Prometheus counter (agent_calls_total{agent, status})

Every LLM call:
  → LangSmith trace (full prompt + response + token usage)
  → Prometheus: llm_calls_total, llm_tokens_total, llm_cost_usd_total
  → Redis: per-JD cost accumulator (TTL 30d)

Every tool call:
  → Prometheus: tool_calls_total{tool, status}, tool_latency_seconds

Dashboard (Grafana):
  → Daily cost vs budget
  → Agent latency p50/p95
  → LLM token consumption by agent
  → Candidates sourced per source
  → JD funnel (open → screened → closed)
```

## Infrastructure

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  PostgreSQL  │  │    Redis    │  │  Pinecone   │
│  (JDs,      │  │  (workflow  │  │  (vector    │
│  candidates,│  │   state,    │  │   store,    │
│  audit)     │  │   cost      │  │   384-dim)  │
│             │  │   tracking) │  │             │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  LangSmith  │  │ Prometheus  │  │   Grafana   │
│  (LLM       │  │ (metrics)   │  │(dashboards) │
│   traces)   │  │             │  │             │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────────────────────────────────────────┐
│           OpenTelemetry Collector               │
│   OTLP gRPC (4317) → Prometheus (8888)          │
└─────────────────────────────────────────────────┘
```

## Kafka Note

Kafka is specified in the tech stack for queue/parallelism.
In this implementation, parallel execution is achieved via Python's
`asyncio.gather()` which is equivalent for the async I/O workload here
(LLM API calls, DB queries). For a production deployment with multiple
backend pods, Kafka would be used to distribute JD processing tasks
across instances, with each pod consuming from a `jd-intake` topic.
The architecture is designed to support this: OrchestratorAgent is
stateless and reads all state from PostgreSQL + Redis.
