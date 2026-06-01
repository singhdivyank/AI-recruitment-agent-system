# Design Decisions — AI Recruitment Agent

## 1. Retry Strategy: Original Prompt Only (Not Full History)

**Decision:** On LLM retry, send only the original `system_prompt + user_prompt`. Never append the previous response or error message to the context.

**Why:** A naive retry that appends "that was wrong, try again" + the prior response doubles the token count on each retry. With 3 retries, a 10K-token prompt becomes 40K tokens on the final attempt — a 4× cost spike per failure. By resending only the original prompt, retries are token-neutral. The tradeoff is that the model doesn't have the failed attempt as context, but for structured JSON extraction tasks this is irrelevant: the failure is usually a formatting error, not a reasoning error.

**Cost impact:** Prevents $4 → $40 per-JD bill spikes during transient API failures.

---

## 2. Model Routing: Gemini Pro vs Flash

**Decision:** Use Gemini 2.5 Pro for JD parsing and candidate screening. Use Gemini Flash for compliance, rationale generation, and outreach drafting.

| Task                                     | Model | Reason                                                                        |
| ---------------------------------------- | ----- | ----------------------------------------------------------------------------- |
| JD Intake (parse JD → structured fields) | Pro   | Precision matters; wrong seniority/skills poisons the whole pipeline          |
| Compliance detection                     | Flash | Binary classification; Flash is sufficient and 35× cheaper                    |
| Candidate Screening                      | Pro   | Complex multi-criterion reasoning; quality directly impacts shortlist quality |
| Ranking rationale                        | Flash | Summarization from existing scores; no new reasoning required                 |
| Outreach drafting                        | Flash | Creative writing; Flash produces good copy at low cost                        |
| Closure justification                    | Flash | Short summarization task                                                      |

**Why not Pro everywhere?** Pro costs $3.50/$10.50 per 1M tokens. Flash costs $0.10/$0.40. Screening 40 candidates per JD with long prompts (~2K tokens each) costs ~$0.84 with Pro. The same with Flash would cost ~$0.024. We use Pro only where reasoning quality materially affects outcomes.

---

## 3. Deduplication: Union-Find with Multi-Signal Matching

**Decision:** Use Union-Find (disjoint set union) algorithm with priority-ordered matching signals.

**Signal priority:**

1. Email match — definitive (globally unique)
2. Phone match — definitive (last 10 digits)
3. LinkedIn URL handle — definitive (platform-unique)
4. Name + current company — medium confidence (25% collision risk due to common names)

**Why Union-Find vs simple dict lookup?** A candidate appearing on all three platforms would generate 3 separate records. Simple deduplication merges A→B and B→C, but misses A→C unless run in multiple passes. Union-Find handles transitive closure in a single pass at O(n·α(n)) ≈ O(n) time.

**Why NOT embedding similarity for dedup?** Cosine similarity on resume text has high false-positive rate (two "senior Python engineers" in the same city will have similar embeddings). Embedding similarity is used for ranking/retrieval, not identity resolution.

---

## 4. Parallel Sourcing: asyncio.gather vs Kafka

**Decision:** Use `asyncio.gather()` for parallel source fan-out rather than Kafka message queues.

**Why:** For a single-process async FastAPI app, `asyncio.gather()` achieves the same concurrency as Kafka fan-out with zero infrastructure overhead. All three source searches (LinkedIn, Naukri, ATS) run concurrently and the results merge when all complete.

**Kafka is still the right answer for production at scale:** If 100 recruiters submit JDs simultaneously, each triggering a 30-agent workflow, a single-process implementation would queue them. Kafka enables horizontal scaling: multiple backend pods each consuming from a `jd-intake` topic. The architecture is designed for this: OrchestratorAgent is fully stateless and reads/writes all state to PostgreSQL + Redis.

**`return_exceptions=True`:** A critical detail. Without this, if Naukri search fails, the entire gather() fails and no candidates are returned. With `return_exceptions=True`, LinkedIn and ATS results are preserved and the pipeline continues.

---

## 5. RAG Pipeline: Pinecone + CrossEncoder Reranking

**Decision:** Two-stage retrieval — semantic search in Pinecone, then CrossEncoder reranking.

**Why two stages?** Pinecone's cosine similarity on `all-MiniLM-L6-v2` embeddings is fast but imprecise: it captures semantic similarity at the sentence-level but misses nuanced query-document relevance. CrossEncoder (`ms-marco-MiniLM-L-6-v2`) reads the query and document together, giving much higher quality relevance scores — but it's slow and can't scale to thousands of candidates. Two-stage solves this: Pinecone narrows from N→50, CrossEncoder re-ranks 50→20.

**Embedding text construction:** We concatenate summary + skills list + work history titles + education rather than embedding raw resume text. This puts the highest-signal fields first in the embedding space.

**Metadata pre-filtering:** Pinecone metadata filters (location, experience_years) applied at query time reduce the candidate pool before similarity search. This avoids retrieving geographically inappropriate candidates even if their skill embeddings are similar.

---

## 6. Sourcing Dataset: HuggingFace json_resume_dataset

**Decision:** Partition the HF dataset 40/30/30 across LinkedIn/Naukri/ATS simulators with a 20-profile overlap between LinkedIn and Naukri.

**Why overlapping partitions?** The overlap is intentional: it generates duplicate candidates that the deduplication agent must resolve. This tests the full pipeline correctly and validates the Union-Find deduplication logic.

**Why shuffle within partitions?** Real search APIs return results in non-deterministic order (ranking, ad-weighted, A/B tested). Shuffling simulates this — our ranking shouldn't be sensitive to source ordering.

**Synthetic fallback:** If the HF dataset is unavailable (network issue, token required), Faker generates 500 synthetic profiles. The pipeline is tested to work with synthetic data, ensuring CI/CD can run without HF credentials.

---

## 7. Screening Semaphore: 5 Concurrent LLM Calls

**Decision:** `asyncio.Semaphore(5)` caps concurrent screening LLM calls.

**Why 5?** Gemini API has rate limits (requests per minute vary by tier). 5 concurrent calls at ~2K tokens each = ~10K tokens in-flight. At Gemini Pro processing speed (~300 tokens/sec), this completes in ~7 seconds. Going higher risks 429 rate limit errors, which trigger retries and increase cost. Going lower (1-2) makes screening linear and slow.

**Outreach uses Semaphore(3):** Outreach prompts are longer (includes candidate + JD context). Lower concurrency avoids rate limit pressure.

---

## 8. Cost Guardrails via Redis

**Decision:** Track per-JD and daily costs in Redis with TTL-based expiry. Check limits BEFORE every LLM call.

**Why Redis, not PostgreSQL?** Cost checks happen on every LLM call (potentially 40+ times per JD). Redis INCRBYFLOAT is atomic, sub-millisecond, and designed for high-frequency counters. PostgreSQL would require a transaction for each update.

**Why pre-check, not post-check?** Post-checking ("you went over budget") is useless — the money is already spent. Pre-checking estimates the cost of the next call and aborts if it would breach the limit.

**TTL strategy:**

- `cost:jd:{id}` → 30-day TTL (JD lifecycle, closed after hiring)
- `cost:daily` → 24-hour TTL (resets automatically at midnight UTC)

---

## 9. Human-in-the-Loop: Recruiter Approval Gate

**Decision:** Pipeline runs fully automated through shortlist generation. Recruiter must explicitly call `POST /jds/{id}/close` to finalize selection.

**Why not full automation?** Hiring decisions have legal and organizational consequences. Even a 95%-accurate AI recommendation could result in a discriminatory hire if auto-confirmed. The recruiter approval gate ensures accountability and provides a mandatory compliance checkpoint.

**Top-pick recommendation:** The system still recommends a top pick (highlighted in the UI) so the recruiter doesn't need to evaluate all 10 shortlisted candidates from scratch. The AI does the ranking; the human confirms.

---

## 10. LangGraph vs Hand-Coded State Machine

**Decision:** Use LangGraph's `StateGraph` for workflow orchestration.

**Why:** A hand-coded state machine requires explicit state management, error propagation, and branching logic scattered across the codebase. LangGraph provides:

- Declarative graph definition (easy to visualize/modify)
- Built-in state passing between nodes
- Conditional edges for compliance routing
- First-class async support
- LangSmith integration for workflow tracing

**Tradeoff:** LangGraph adds a dependency and its API has been changing across versions. Pinned to `langgraph==0.1.5` for stability.
