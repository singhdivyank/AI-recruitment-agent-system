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
│   │  (Pro LLM)   │    │ (Flash LLM)  │                              │
│   └──────────────┘    └──────┬───────┘                             │
│                              │ pass / fail                          │
│                         ┌────▼─────┐                               │
│                         │ Sourcing │ (fan-out below)                │
│                         │  Agent   │                               │
│                         └────┬─────┘                               │
│                              │ asyncio.gather() — no semaphore      │
│          ┌───────────────────┼───────────────────┐                 │
│          ▼                   ▼                   ▼                  │
│    ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│    │ LinkedIn │       │  Naukri  │       │   ATS    │              │
│    │   MCP    │       │   MCP    │       │   MCP    │              │
│    │ (SSE/    │       │ (SSE/    │       │ (SSE/    │              │
│    │ port 8001│       │ port 8002│       │ port 8003│              │
│    └──────────┘       └──────────┘       └──────────┘              │
│          │                   │                   │                  │
│          └───────────────────┼───────────────────┘                 │
│                              │ (fan-in: merge + return_exceptions)  │
│                         ┌────▼──────────┐                          │
│                         │ Normalization │                           │
│                         │    Agent      │                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │ Deduplication │  Union-Find algorithm     │
│                         │    Agent      │  signals: email, phone,   │
│                         │               │  LinkedIn URL, name+co    │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │  RAG Ingest   │  ←── pgvector            │
│                         │  (batch upsert│       (PostgreSQL)        │
│                         │   IVFFlat idx)│                           │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │  RAG Retrieve │  cosine ANN + metadata   │
│                         │  + Re-rank    │  filters → CrossEncoder  │
│                         │               │  top-50 → top-20 → top-40│
│                         └────┬──────────┘                          │
│                              │ top-40 candidates                    │
│                              │ Semaphore(5) — max 5 concurrent LLM  │
│     ┌───────────────────────┬┴──────────────────────────┐          │
│     ▼           ▼           ▼           ▼           ▼   ▼          │
│ ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐         │
│ │Screen │   │Screen │   │Screen │   │Screen │   │Screen │  ...    │
│ │  C1   │   │  C2   │   │  C3   │   │  C4   │   │  C5   │         │
│ │(Pro)  │   │(Pro)  │   │(Pro)  │   │(Pro)  │   │(Pro)  │         │
│ └───────┘   └───────┘   └───────┘   └───────┘   └───────┘         │
│                              │ (fan-in)                             │
│                         ┌────▼──────────┐                          │
│                         │   Ranking     │  weighted formula:        │
│                         │    Agent      │  0.4·skill + 0.2·exp     │
│                         │               │  + 0.2·semantic           │
│                         │               │  + 0.1·location           │
│                         │               │  + 0.1·recruiter_pref     │
│                         │               │  top-10 shortlisted       │
│                         └────┬──────────┘                          │
│                    Semaphore(3) — rationale generation              │
│          ┌───────────────────┼───────────────────┐                 │
│          ▼                   ▼                   ▼                  │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│   │Rationale │       │Rationale │       │Rationale │              │
│   │  C1      │       │  C2      │       │  C3      │  ...         │
│   │(Flash)   │       │(Flash)   │       │(Flash)   │              │
│   └──────────┘       └──────────┘       └──────────┘              │
│                              │ Top Pick selected (Pro LLM)          │
│                         ┌────▼──────────┐                          │
│                         │   Outreach    │  Semaphore(3)            │
│                         │    Agent      │  draft per candidate      │
│                         │  (Flash LLM)  │  (fan-out/fan-in)        │
│                         └────┬──────────┘                          │
│                              │                                      │
│                         ┌────▼──────────┐                          │
│                         │   Recruiter   │                           │
│                         │   Approval    │  ← human-in-the-loop     │
│                         └────┬──────────┘                          │
│                              │ POST /jds/{id}/close                 │
│                         ┌────▼──────────┐                          │
│                         │   Closure     │                           │
│                         │    Agent      │  (Flash LLM)             │
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
   │                  │                  │              │──SSE────────────▶│ LinkedIn MCP
   │                  │                  │              │──SSE────────────▶│ Naukri MCP
   │                  │                  │              │──SSE────────────▶│ ATS MCP
   │                  │                  │              │◀───────profiles─│
   │                  │                  │◀─all profiles│                 │
   │                  │                  │──Normalize──▶│                 │
   │                  │                  │──Deduplicate▶│                 │
   │                  │                  │──RAG ingest─▶│──upsert────────▶│ pgvector (Postgres)
   │                  │                  │──Screening──▶│──embed─────────▶│ Inference Service
   │                  │                  │              │──ANN retrieve──▶│ pgvector (Postgres)
   │                  │                  │              │──rerank────────▶│ Inference Service
   │                  │                  │              │──gather(screen)─▶│ Gemini Pro
   │                  │                  │◀─scores──────│                 │
   │                  │                  │──Ranking────▶│──Gemini Flash   │
   │                  │                  │──Outreach───▶│──Gemini Flash   │
   │                  │                  │◀─shortlist───│                 │
   │──GET /shortlist─▶│                  │              │                 │
   │◀─ranked list─────│                  │              │                 │
   │──POST /close────▶│                  │              │                 │
   │                  │──ClosureAgent───▶│──audit log──▶│                 │
   │◀─closed──────────│                  │              │                 │
```

## Retrieval Flow

```
JD Title + Skills + Description
              │
              ▼
  Inference Service /embed
  (all-MiniLM-L6-v2, 384-dim)
              │
              ▼
     query vector [384-dim]
              │
              ├── Metadata Pre-filter ─────────────────▶ PostgreSQL
              │   • experience_years >= min_years          (SQL WHERE)
              │   • experience_years <= max_years
              │   • location ILIKE '%location%'
              │
              └── ANN Semantic Search ─────────────────▶ PostgreSQL
                  (pgvector IVFFlat, cosine distance)      (pgvector)
                            │
                            ▼
                       Top-50 matches
                            │
                            ▼
              Inference Service /rerank
              (CrossEncoder ms-marco-MiniLM-L-6-v2)
              scores each (query_text, profile_text) pair
                            │
                            ▼
                       Top-20 re-ranked
                            │
                            ▼
              + remaining un-indexed profiles appended
                            │
                            ▼
                    Top-40 → Screening Agent
```

## MCP Transport

```
SourcingAgent
     │
     ├── MCP SDK ClientSession ──SSE──▶ LinkedIn MCP (port 8001)
     │                                    tools: search_profiles
     │                                           fetch_profile
     │
     ├── MCP SDK ClientSession ──SSE──▶ Naukri MCP (port 8002)
     │                                    tools: search_profiles
     │                                           fetch_profile
     │
     └── MCP SDK ClientSession ──SSE──▶ ATS MCP (port 8003)
                                          tools: search_profiles
                                                 fetch_profile
                                                 update_status  ← write-back only on ATS

Each MCP server:
  - Backed by HuggingFace json_resume_dataset (partitioned by source)
  - LinkedIn: rows 0–40%
  - Naukri:   rows 38–70%  (2% overlap with LinkedIn → intentional dedup test)
  - ATS:      rows 70–100%
  - Paginated (page, page_size), max 3 pages per source
  - Source failure does not block pipeline (return_exceptions=True)
```

## LLM Model Routing

```
Task                          Model              Reason
─────────────────────────────────────────────────────────────────
JD parsing (intake)           Gemini 2.5 Pro     Structured extraction
Compliance check              Gemini 2.0 Flash   Binary classification
Candidate screening           Gemini 2.5 Pro     Quality-critical scoring
Rationale generation          Gemini 2.0 Flash   Summarisation
Top Pick selection            Gemini 2.5 Pro     Comparative reasoning
Outreach drafting             Gemini 2.0 Flash   Text generation
Closure justification         Gemini 2.0 Flash   Text generation
```

## Tool Calling Flow

```
Agent calls tool → tool executes → result returned → state updated

Tools used per agent:
  SourcingAgent:    search_profiles (LinkedIn/Naukri/ATS via MCP SSE)
                    update_status (ATS write-back, first 10 candidates only)
  ScreeningAgent:   rag_retrieve (pgvector), rerank (inference service),
                    score_candidate (Gemini Pro per-criterion)
  OutreachAgent:    draft_outreach (Gemini Flash)
  ClosureAgent:     update_jd_state, close_jd (DB updates)
                    build_justification (Gemini Flash)

All tools:
  • Handle pagination (page, page_size params)
  • Return [] on empty results (never raise on empty)
  • Wrapped in _wrap() decorator → records latency to Prometheus
  • Source failure isolated (return_exceptions=True in asyncio.gather)
```

## State Transitions (JD lifecycle)

```
                   ┌──────────────────────────────────────┐
                   │           compliance fail             │
                   ▼                                       │
OPEN ──intake──▶ OPEN ──sourcing starts──▶ SOURCING ──────┤
                                               │           │
                                               ▼           │
                                           SCREENING       │
                                               │           │
                                               ▼           │
                                          SHORTLISTED      │
                                               │           │
                                    recruiter confirms     │
                                               │           │
                                               ▼           │
                                            CLOSED         │
                                                           │
                                          REJECTED ◀───────┘

Note: JD is created with status OPEN by JDIntakeAgent.
      Status is updated in-place by each agent (no DRAFT state used).
      SCREENING status is not explicitly set; the transition goes
      SOURCING → SHORTLISTED once ranking completes.
```

## Retry Strategy

```
LLM calls:
  max_retries = 3
  backoff = exponential (1s, 2s, 4s)  [2^attempt seconds]
  CRITICAL: each retry sends ORIGINAL prompt only (not appended history)
  → prevents token explosion from retry storms
  CostGuardrailError is never retried

Tool calls (MCP sourcing):
  max_pages = 3 per source
  empty page = stop paginating (exhausted)
  MCPCallError = stop source, use results so far
  failed source does not block pipeline (return_exceptions=True)

Cost guardrails (checked BEFORE every LLM call via Redis):
  per_jd_token_cap  = 500,000 tokens
  per_jd_cost_cap   = $5.00
  daily_budget_cap  = $100.00
  → CostGuardrailError raised immediately, never retried
  → Tracked in Redis with 30d TTL (per-JD), 24h TTL (daily)
```

## Scoring Formula

```
final_score = 0.4 × skill_match
            + 0.2 × experience_score
            + 0.2 × semantic_similarity   (overall RAG/screening score)
            + 0.1 × location_fit
            + 0.1 × recruiter_preference  (from score overrides, default 5.0)

skill_match = (must_have_avg × 3 + nice_to_have_avg) / 4
              must-haves weighted 3× over nice-to-haves

All scores on 0–10 scale. Top-10 candidates shortlisted (SHORTLIST_N = 10).
Recruiter can override any criterion score via POST /jds/{id}/candidates/{cid}/override.
```

## Deduplication Strategy

```
Algorithm: Union-Find (path-compressed)

Signals matched in priority order:
  1. Email match          (High confidence)  → key: "email:{normalised_email}"
  2. Phone match          (High confidence)  → key: "phone:{last_10_digits}"
  3. LinkedIn URL match   (High confidence)  → key: "linkedin:{handle}"
  4. Name + company       (Medium)           → key: "namecompany:{md5(name:company)}"

On merge: richest data wins
  • More source_profiles → union of sources
  • Higher experience_years → kept
  • Longer employment_history → kept
  • Missing fields filled from duplicate

Intentional 2% LinkedIn/Naukri overlap in dataset exercises dedup path.
```

## Observability Flow

```
Every agent call:
  → structlog JSON log (timestamp, agent, jd_id, latency, status)
  → OTel span (trace_id propagated through entire workflow)
  → Prometheus counter (agent_calls_total{agent_name, status})
  → ACTIVE_WORKFLOWS gauge (inc on start, dec on finish/error)

Every LLM call:
  → LangSmith trace (full prompt + response + token usage)
  → Prometheus: llm_calls_total, llm_tokens_total, llm_cost_usd_total
  → Redis: per-JD cost accumulator (TTL 30d) + daily budget (TTL 24h)

Every tool call:
  → Prometheus: tool_calls_total{tool_name, status}, tool_latency_seconds
  → TOOL_FAILURES counter on error

Evaluation endpoints (GET /api/v1/eval/*):
  → Retrieval:     Precision@k, Recall@k, NDCG@k
  → Deduplication: merge_rate, candidates_from_multiple_sources
  → Screening:     MAE vs recruiter overrides, agreement %
  → Ranking:       Top-1 Accuracy, NDCG@10
  → Workflow:      completion_rate, avg_cost_per_jd
  → Cost:          tokens/JD, cost/JD, cost/candidate
```

## Infrastructure

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                              │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │  PostgreSQL  │  │    Redis    │  │     pgvector extension      │ │
│  │  pg16 +      │  │  7-alpine   │  │  profile_embeddings table   │ │
│  │  pgvector    │  │  cost/token │  │  IVFFlat cosine index       │ │
│  │  (port 5432) │  │  tracking   │  │  384-dim vectors            │ │
│  │  JDs,cands,  │  │  (port 6379)│  └─────────────────────────────┘ │
│  │  audit,      │  │             │                                 │ │
│  │  embeddings  │  └─────────────┘                                 │ │
│  └─────────────┘                                                   │ │
│                                                                     │ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │Elasticsearch│  │    Kibana   │  │  Inference  │               │ │
│  │  8.13.0     │  │  8.13.0     │  │  Service    │               │ │
│  │  BM25 index │  │  (port 5601)│  │  (port 8080)│               │ │
│  │  (port 9200)│  │             │  │  /embed     │               │ │
│  │  available  │  │             │  │  /rerank    │               │ │
│  │  not used   │  │             │  │  MiniLM +   │               │ │
│  │  in RAG yet │  │             │  │  CrossEncoder│              │ │
│  └─────────────┘  └─────────────┘  └─────────────┘               │ │
│                                                                     │ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │ │
│  │  LangSmith  │  │ Prometheus  │  │   Grafana               │   │ │
│  │  (external) │  │ (port 9090) │  │  (port 3001)            │   │ │
│  │  LLM traces │  │  metrics    │  │   dashboards            │   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘   │ │
│                                                                     │ │
│  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │           OpenTelemetry Collector                            │  │ │
│  │   OTLP gRPC (4317) | OTLP HTTP (4318) | Prom (8888)         │  │ │
│  └──────────────────────────────────────────────────────────────┘  │ │
└─────────────────────────────────────────────────────────────────────┘
```

## Container Architecture

```
Backend container (port 8000)        Inference Service container (port 8080)
  FastAPI + LangGraph               ┌──────────────────────────────────────┐
  All agents                    ───▶│  POST /embed   (all-MiniLM-L6-v2)   │
  No torch / no ML models           │  POST /rerank  (CrossEncoder)        │
  Calls inference service           │  GET  /health                        │
  over HTTP for embeddings          │  Model weights cached in /models vol │
  and reranking                     └──────────────────────────────────────┘

MCP Server containers (ports 8001–8003)
  LinkedIn MCP  → search_profiles, fetch_profile
  Naukri MCP    → search_profiles, fetch_profile
  ATS MCP       → search_profiles, fetch_profile, update_status
  All backed by HuggingFace json_resume_dataset
  All communicate over SSE (FastMCP transport)
```

## Kafka Note

Kafka is specified in the tech stack for queue/parallelism.
In this implementation, parallel execution is achieved via Python's
`asyncio.gather()` which is sufficient for the async I/O workload here
(LLM API calls, DB queries, MCP SSE calls). For a production deployment
with multiple backend pods, Kafka would distribute JD processing tasks
across instances, with each pod consuming from a `jd-intake` topic.
The architecture supports this: OrchestratorAgent is stateless and reads
all state from PostgreSQL + Redis. The LangGraph StateGraph is compiled
once per process and invoked per JD.