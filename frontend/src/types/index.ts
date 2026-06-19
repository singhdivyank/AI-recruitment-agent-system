export type JDStatus =
  | "OPEN" | "SOURCING" | "SCREENING" | "SHORTLISTED"
  | "CLOSED" | "REJECTED" | "PROCESSING";

export type CandidateStatus =
  | "SOURCED" | "NORMALIZED" | "SCREENED" | "SHORTLISTED"
  | "SELECTED" | "REJECTED" | "PROCESSING";

export interface JD {
  jd_id: string;
  title: string;
  description: string;
  status: JDStatus;
  location: string;
  employment_type: string;
  must_have_skills: string[];
  nice_to_have_skills: string[];
  years_experience: { min: number; max: number };
  target_hiring_date: string;
  total_candidates: number;
  shortlisted_count: number;
  estimated_cost_usd: number;
  token_usage: number;
  compliance_passed: boolean | null;
  compliance_flags: string[];
  parsed_data?: {
    seniority_level: string;
    remote_ok: boolean;
    hiring_urgency: string;
  };
  created_at: string;
}

export interface CriterionScore {
  criterion: string;
  score: number;
  reasoning: string;
}

export interface ScreeningData {
  criterion_scores: CriterionScore[];
  strengths: string[];
  gaps: string[];
  overall_reasoning: string;
}

export interface Candidate {
  candidate_id: string;
  name: string;
  email?: string;
  location: string;
  experience_years: number;
  skills: string[];
  status: CandidateStatus;
  overall_score?: number;
  source_profiles?: { source: string; url?: string }[];
  screening_data?: ScreeningData;
  outreach_draft?: string;
}

export interface RankedCandidate {
  rank: number;
  final_score: number;
  candidate: Candidate;
  screening?: ScreeningData;
  outreach_draft?: string;
}

export interface CostMetrics {
  daily_cost_usd: number;
  daily_budget_usd: number;
  budget_used_pct: number;
  total_tokens: number;
}

export interface AuditEntry {
  audit_id: string;
  action: string;
  reason?: string;
  closed_at: string;
  agent?: string;
}

export interface AgentNode {
  id: string;
  label: string;
  description: string;
  status: "idle" | "running" | "done" | "pending" | "failed";
  avg_latency_ms?: number;
  success_rate?: number;
  total_calls?: number;
}

export interface EvalMetrics {
  recall_at_10?: number;
  precision_at_10?: number;
  ndcg_at_10?: number;
  mrr?: number;
  human_agreement?: number;
  hallucination_rate?: number;
  grounding_score?: number;
  top1_accuracy?: number;
  top3_accuracy?: number;
  recommendation_acceptance?: number;
}

export interface MCPProvider {
  id: string;
  name: string;
  status: "healthy" | "degraded" | "down";
  latency_ms: number;
  tool_calls: number;
  success_rate: number;
  availability: number;
}