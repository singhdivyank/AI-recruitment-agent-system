# Design Decisions — AI Recruitment Agent

## 1. Retry Strategy: Original Prompt Only (Not Full History)

**Decision:** On LLM retry, send only the original `system_prompt + user_prompt`. Never append the previous response or error message to the context.

**Why:** A naive retry that appends "that was wrong, try again" + the prior response doubles the token count on each retry. With 3 retries, a 10K-token prompt becomes 40K tokens on the final attempt — a 4× cost spike per failure. By resending only the original prompt, retries are token-neutral. The tradeoff is that the model doesn't have the failed attempt as context, but for structured JSON extraction tasks this is irrelevant: the failure is usually a formatting error, not a reasoning error.

**Implementation detail:** `call_json()` appends `"\n\nRespond ONLY with valid JSON, no markdown fences."` to the system prompt. Each retry re-sends this combined prompt fresh — no history accumulation.

**Cost impact:** Prevents $4 → $40 per-JD bill spikes during transient API failures.

---

## 2. Model Routing: Gemini Pro vs Flash

**Decision:** Use Gemini 2.5 Pro for JD parsing, candidate screening, and top-pick selection. Use Gemini 2.0 Flash for compliance, rationale generation, outreach drafting, and closure justification.

| Task                                     | Model | Reason                                                                        |
| ---------------------------------------- | ----- | ----------------------------------------------------------------------------- |
| JD Intake (parse JD → structured fields) | Pro   | Precision matters; wrong seniority/skills poisons the whole pipeline          |
| Compliance detection                     | Flash | Binary classification; Flash is sufficient and 35× cheaper on input tokens    |
| Candidate Screening                      | Pro   | Complex multi-criterion reasoning; quality directly impacts shortlist quality |
| Ranking rationale generation             | Flash | Summarisation from existing scores; no new reasoning required                 |
| Top Pick selection                       | Pro   | Comparative reasoning across candidates; quality matters for recommendation   |
| Outreach drafting                        | Flash | Creative writing; Flash produces good copy at low cost                        |
| Closure justification                    | Flash | Short summarisation task                                                      |

**Why not Pro everywhere?** Pro costs $3.50/$10.50 per 1M input/output tokens. Flash costs $0.10/$0.40 — a 35× input and 26× output cost difference. Screening 40 candidates with ~2K input tokens each costs ~$0.28 with Pro vs ~$0.008 with Flash. We use Pro only where reasoning quality materially affects outcomes.

---

## 3. Deduplication: Union-Find with Multi-Signal Matching

**Decision:** Use Union-Find (disjoint set union) algorithm with priority-ordered matching signals.

**Signal priority:**

1. Email match — definitive (globally unique)
2. Phone match — definitive (last 10 digits normalised)
3. LinkedIn URL handle — definitive (platform-unique)
4. Name + current company — medium confidence (collision risk with common names)

**Why Union-Find vs simple dict lookup?** A candidate appearing on all three platforms generates 3 separate records. Simple deduplication merges A→B and B→C but misses A→C unless run in multiple passes. Union-Find handles transitive closure in a single pass at O(n·α(n)) ≈ O(n) time with path compression.

**Why NOT embedding similarity for dedup?** Cosine similarity on resume text has a high false-positive rate (two "senior Python engineers" in the same city will have similar embeddings). Embedding similarity is used for ranking/retrieval, not identity resolution.

**Merge strategy:** On merge, richest data wins — more source_profiles, higher experience_years, longer employment_history, and missing fields filled from the duplicate.

---

## 4. Parallel Sourcing: asyncio.gather vs Kafka

**Decision:** Use `asyncio.gather()` for parallel source fan-out rather than Kafka message queues.

**Why:** For a single-process async FastAPI app, `asyncio.gather()` achieves the same concurrency as Kafka fan-out with zero infrastructure overhead. All three MCP source searches (LinkedIn, Naukri, ATS) run concurrently over SSE and results merge when all complete.

**Kafka is still the right answer for production at scale:** If 100 recruiters submit JDs simultaneously, each triggering a full workflow, a single-process implementation would queue them. Kafka enables horizontal scaling: multiple backend pods each consuming from a `jd-intake` topic. The architecture supports this: OrchestratorAgent is fully stateless and reads/writes all state to PostgreSQL + Redis.

**`return_exceptions=True`:** A critical detail. Without this, if Naukri MCP search fails, the entire `gather()` raises and no candidates are returned. With `return_exceptions=True`, LinkedIn and ATS results are preserved and the pipeline continues with a partial candidate pool.

---

## 5. RAG Pipeline: pgvector over Pinecone

**Decision:** Use pgvector inside the existing PostgreSQL container rather than Pinecone as an external vector store.

**Why pgvector over Pinecone for this project:**

- Runs inside the existing Docker postgres container — no extra service
- No external API key or account required for local development
- Full SQL expressiveness for metadata pre-filters (ILIKE, range queries, array operators)
- Atomic with the rest of the DB — same transaction boundary as candidate data
- Pinecone's starter plan restricts to AWS only; pgvector has no such limits

**Two-stage retrieval:** Vector search alone (cosine similarity on `all-MiniLM-L6-v2` embeddings) is fast but imprecise — it captures semantic similarity at the sentence level but misses nuanced query-document relevance. CrossEncoder (`ms-marco-MiniLM-L-6-v2`) reads query and document together, giving much higher quality relevance scores, but is slow and can't scale to thousands of candidates. Two-stage solves this:

```
pgvector ANN retrieval  →  top-60 matches
        ↓
CrossEncoder rerank     →  top-30 re-ranked
        ↓
+ un-indexed profiles appended  →  top-40 sent to Screening Agent
```

Note: `consts.py` defines `TOP_K_RETRIEVE = 50` and `TOP_K_RERANK = 20` as defaults, but `ScreeningAgent` calls `rag.retrieve(top_k=60)` and `rag.rerank(top_k=30)` directly, overriding the defaults for a wider initial pool.

**Index:** IVFFlat cosine index with `IVFFLAT_LISTS = 50`. Index creation requires a minimum row count before building; the pipeline checks this on each ingest batch.

**Embedding text construction:** Concatenates summary + skills + work history titles + education rather than raw resume text, putting the highest-signal fields first in the embedding space.

---

## 6. Sourcing Dataset: HuggingFace json_resume_dataset

**Decision:** Partition the HF dataset 40%/30%/30% across LinkedIn/Naukri/ATS simulators with a 20-profile overlap between LinkedIn and Naukri.

**Actual partition boundaries:**

- LinkedIn: rows 0–40%
- Naukri: rows (40% − 20 rows) to 70% ← 20-row overlap with LinkedIn
- ATS: rows 70–100%

**Why overlapping partitions?** The overlap is intentional: it generates duplicate candidates that the deduplication agent must resolve, exercising the Union-Find logic with real cross-source duplicates. Their `candidate_id` is a deterministic MD5 of email, so the dedup will correctly merge them via email key.

**Why shuffle within partitions?** Real search APIs return results in non-deterministic order (ranking, ad-weighted, A/B tested). `random.shuffle()` simulates this — our pipeline shouldn't be sensitive to source ordering.

**Synthetic fallback:** If the HF dataset is unavailable (network issue, token required), `Faker` generates 500 synthetic profiles, ensuring the pipeline runs without HF credentials in CI/CD.

---

## 7. Screening Semaphore: 5 Concurrent LLM Calls

**Decision:** `asyncio.Semaphore(5)` caps concurrent screening LLM calls at 5. Outreach and rationale generation use `Semaphore(3)`.

**Why 5 for screening?** Gemini API has rate limits (requests per minute vary by tier). 5 concurrent calls at ~2K tokens each = ~10K tokens in-flight simultaneously. Going higher risks 429 rate limit errors which trigger retries and increase cost. Going lower makes screening near-linear and slow.

**Why 3 for outreach and rationale?** Outreach prompts include full JD + candidate context and are longer than screening prompts. Lower concurrency reduces rate-limit pressure on the same API quota.

**Why no semaphore on sourcing?** MCP source calls go to three different servers (LinkedIn, Naukri, ATS) over SSE. They don't share an API rate limit, so all three run fully in parallel with no semaphore.

---

## 8. Cost Guardrails via Redis

**Decision:** Track per-JD and daily costs in Redis with TTL-based expiry. Check limits BEFORE every LLM call.

**Why Redis, not PostgreSQL?** Cost checks happen on every LLM call — potentially 40+ times per JD during screening. Redis `INCRBYFLOAT` and `INCRBY` are atomic, sub-millisecond, and designed for high-frequency counters. PostgreSQL would require a row lock and transaction for each update. The implementation uses a Redis pipeline to batch the increment + expire commands into a single round trip.

**Why pre-check, not post-check?** Post-checking ("you went over budget") is useless — the money is already spent. Pre-checking estimates the cost of the next call using the prompt word count and aborts with `CostGuardrailError` if it would breach the limit. `CostGuardrailError` is never retried.

**Three independent limits (all must pass):**

| Limit            | Value          | Redis key           | TTL      |
| ---------------- | -------------- | ------------------- | -------- |
| Per-JD cost cap  | $5.00          | `cost:jd:{jd_id}`   | 30 days  |
| Per-JD token cap | 500,000 tokens | `tokens:jd:{jd_id}` | 30 days  |
| Daily budget cap | $100.00        | `cost:daily`        | 24 hours |

---

## 9. Human-in-the-Loop: Recruiter Approval Gate

**Decision:** Pipeline runs fully automated through shortlist generation. Recruiter must explicitly call `POST /jds/{id}/close` to finalise selection.

**Why not full automation?** Hiring decisions have legal and organisational consequences. Even a 95%-accurate AI recommendation could result in a discriminatory or poor hire if auto-confirmed. The recruiter approval gate ensures accountability and provides a mandatory compliance checkpoint.

**Top-pick recommendation:** The system recommends a top pick (via `_select_top_pick` using Gemini Pro, highlighted in the UI) so the recruiter doesn't need to evaluate all 10 shortlisted candidates from scratch. The AI does the ranking; the human confirms.

**HITL override mechanism:** Recruiters can also override individual criterion scores via `POST /jds/{id}/candidates/{cid}/override` before the shortlist is finalised. Score overrides feed into the `recruiter_preference` weight (0.1) in the final scoring formula and are stored in `RecruiterFeedbackModel` for future evaluation.

---

## 10. LangGraph vs Hand-Coded State Machine

**Decision:** Use LangGraph's `StateGraph` for workflow orchestration.

**Why:** A hand-coded state machine requires explicit state management, error propagation, and branching logic scattered across the codebase. LangGraph provides:

- Declarative graph definition (easy to visualise/modify topology)
- Built-in state passing between nodes via `WorkflowState` Pydantic model
- Conditional edges for compliance pass/fail routing (`compliance_router`)
- First-class async support (`ainvoke`)
- LangSmith integration for full workflow tracing

**Implementation:** The graph is compiled once in `OrchestratorAgent.__init__` via `build_graph()` and reused across JD invocations. Each node wraps an agent's `run()` method, serialising/deserialising `WorkflowState` via `model_dump()` / `WorkflowState(**state)` at each boundary since LangGraph passes plain dicts between nodes.

**Tradeoff:** LangGraph adds a dependency whose API has been evolving across versions. The `StateGraph(dict)` typing (rather than a typed state class) is used to avoid LangGraph version compatibility issues with Pydantic v2 state schemas.
