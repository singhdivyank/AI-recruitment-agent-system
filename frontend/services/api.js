import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// ── JD API ────────────────────────────────────────────────────

export const createJD = (data) => api.post("/api/v1/jds", data).then((r) => r.data);

export const listJDs = (status) =>
  api.get("/api/v1/jds", { params: status ? { status } : {} }).then((r) => r.data);

export const getJD = (jdId) => api.get(`/api/v1/jds/${jdId}`).then((r) => r.data);

export const getShortlist = (jdId) =>
  api.get(`/api/v1/jds/${jdId}/shortlist`).then((r) => r.data);

export const closeJD = (jdId, data) =>
  api.post(`/api/v1/jds/${jdId}/close`, data).then((r) => r.data);

export const getAuditLog = (jdId) =>
  api.get(`/api/v1/jds/${jdId}/audit`).then((r) => r.data);

// ── Candidate API ─────────────────────────────────────────────

export const listCandidates = (jdId, status) =>
  api
    .get(`/api/v1/jds/${jdId}/candidates`, { params: status ? { status } : {} })
    .then((r) => r.data);

export const getCandidate = (candidateId) =>
  api.get(`/api/v1/candidates/${candidateId}`).then((r) => r.data);

// ── Metrics ───────────────────────────────────────────────────

export const getCostMetrics = () =>
  api.get("/api/v1/metrics/cost").then((r) => r.data);

export const getHealth = () => api.get("/health").then((r) => r.data);

// ── HITL / Overrides ──────────────────────────────────────────

export const overrideCandidateScores = (jdId, candidateId, data) =>
  api.post(`/api/v1/jds/${jdId}/candidates/${candidateId}/override`, data).then((r) => r.data);

// ── Conversations ─────────────────────────────────────────────

export const sendConversationMessage = (jdId, content) =>
  api.post(`/api/v1/jds/${jdId}/conversation`, { recruiter_id: "recruiter-1", content }).then((r) => r.data);

export const getConversation = (jdId) =>
  api.get(`/api/v1/jds/${jdId}/conversation`).then((r) => r.data);

// ── Outreach History ──────────────────────────────────────────

export const sendOutreach = (candidateId, data) =>
  api.post(`/api/v1/candidates/${candidateId}/outreach`, data).then((r) => r.data);

export const getOutreachHistory = (candidateId) =>
  api.get(`/api/v1/candidates/${candidateId}/outreach`).then((r) => r.data);

// ── Evaluation Metrics ────────────────────────────────────────

export const getRetrievalMetrics = (jdId, k = 10) =>
  api.get(`/api/v1/eval/retrieval/${jdId}`, { params: { k } }).then((r) => r.data);

export const getDeduplicationMetrics = (jdId) =>
  api.get(`/api/v1/eval/deduplication/${jdId}`).then((r) => r.data);

export const getScreeningMetrics = (jdId) =>
  api.get(`/api/v1/eval/screening/${jdId}`).then((r) => r.data);

export const getRankingMetrics = (jdId) =>
  api.get(`/api/v1/eval/ranking/${jdId}`).then((r) => r.data);

export const getWorkflowMetrics = () =>
  api.get(`/api/v1/eval/workflow`).then((r) => r.data);

export const getCostMetricsForJD = (jdId) =>
  api.get(`/api/v1/eval/cost/${jdId}`).then((r) => r.data);