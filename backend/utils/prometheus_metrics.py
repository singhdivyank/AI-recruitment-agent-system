from prometheus_client import Counter, Histogram, Gauge

AGENT_CALLS = Counter(
    "recruitment_agent_calls_total",
    "Total agent invocations",
    ["agent_name", "jd_id", "status"],
)

LLM_CALLS = Counter(
    "recruitment_llm_calls_total",
    "Total LLM API calls",
    ["agent_name", "model", "status"],
)

LLM_TOKENS = Counter(
    "recruitment_llm_tokens_total",
    "Total tokens consumed",
    ["agent_name", "model", "token_type"],
)

LLM_COST = Counter(
    "recruitment_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["agent_name", "model"],
)

LLM_LATENCY = Histogram(
    "recruitment_llm_latency_seconds",
    "LLM call latency in seconds",
    ["agent_name", "model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)

TOOL_CALLS = Counter(
    "recruitment_tool_calls_total",
    "Total tool invocations",
    ["tool_name", "status"],
)

TOOL_LATENCY = Histogram(
    "recruitment_tool_latency_seconds",
    "Tool call latency",
    ["tool_name"],
)

TOOL_FAILURES = Counter(
    "recruitment_tool_failures_total",
    "Total tool call failures",
    ["tool_name"],
)

CANDIDATES_SCREENED = Counter(
    "recruitment_candidate_screened_total",
    "Total candidates that completed screening",
    ["jd_id"],
)

CANDIDATES_RANKED = Counter(
    "recruitment_candidate_ranked_total",
    "Total candidates that were ranked and shortlisted",
    ["jd_id"],
)

SCREENING_DURATION = Histogram(
    "recruitment_screening_duration_seconds",
    "Time to screen all candidates for a JD",
    buckets=[5, 10, 30, 60, 120, 300],
)

RANKING_DURATION = Histogram(
    "recruitment_ranking_duration_seconds",
    "Time to rank and shortlist candidates",
    buckets=[1, 5, 10, 30, 60],
)

SOURCING_DURATION = Histogram(
    "recruitment_sourcing_duration_seconds",
    "Time to complete parallel sourcing across all sources",
    buckets=[1, 2, 5, 10, 30],
)

CANDIDATES_SOURCED = Counter(
    "recruitment_candidates_sourced_total",
    "Candidates retrieved from sources",
    ["source"],
)

TOOL_FAILURES = Counter(
    "recruitment_tool_failures_total",
    "Total tool call failures",
    ["tool_name"],
)

JDS_CREATED = Counter("recruitment_jds_created_total", "JDs submitted")
JDS_CLOSED = Counter("recruitment_jds_closed_total", "JDs closed")
JDS_REJECTED = Counter("recruitment_jds_rejected_compliance_total", "JDs rejected by compliance")

ACTIVE_WORKFLOWS = Gauge(
    "recruitment_active_workflows",
    "Currently running JD workflows",
)

CANDIDATES_SCREENED = Counter(
    "recruitment_candidate_screened_total",
    "Total candidates that completed screening",
    ["jd_id"],
)

CANDIDATES_RANKED = Counter(
    "recruitment_candidate_ranked_total",
    "Total candidates that were ranked and shortlisted",
    ["jd_id"],
)

SCREENING_DURATION = Histogram(
    "recruitment_screening_duration_seconds",
    "Time to screen all candidates for a JD",
    buckets=[5, 10, 30, 60, 120, 300],
)

RANKING_DURATION = Histogram(
    "recruitment_ranking_duration_seconds",
    "Time to rank and shortlist candidates",
    buckets=[1, 5, 10, 30, 60],
)

SOURCING_DURATION = Histogram(
    "recruitment_sourcing_duration_seconds",
    "Time to complete parallel sourcing across all sources",
    buckets=[1, 2, 5, 10, 30],
)
