import axios from "axios";
import type {
  JD, JDStatus, Candidate, CandidateStatus,
  CostMetrics, AuditEntry, RankedCandidate,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

export const createJD = (data: Partial<JD>) =>
  api.post<JD>("/api/v1/jds", data).then((r) => r.data);

export const listJDs = (status?: JDStatus) =>
  api.get<{ items: JD[] }>("/api/v1/jds", { params: status ? { status } : {} }).then((r) => r.data);

export const getJD = (jdId: string) =>
  api.get<JD>(`/api/v1/jds/${jdId}`).then((r) => r.data);

export const getShortlist = (jdId: string) =>
  api.get<{ shortlist: RankedCandidate[] }>(`/api/v1/jds/${jdId}/shortlist`).then((r) => r.data);

export const closeJD = (jdId: string, data: object) =>
  api.post(`/api/v1/jds/${jdId}/close`, data).then((r) => r.data);

export const getAuditLog = (jdId: string) =>
  api.get<{ audit_log: AuditEntry[] }>(`/api/v1/jds/${jdId}/audit`).then((r) => r.data);

export const listCandidates = (jdId: string, status?: CandidateStatus) =>
  api.get<{ items: Candidate[] }>(`/api/v1/jds/${jdId}/candidates`, {
    params: status ? { status } : {},
  }).then((r) => r.data);

export const getCandidate = (candidateId: string) =>
  api.get<Candidate>(`/api/v1/candidates/${candidateId}`).then((r) => r.data);

export const getCostMetrics = () =>
  api.get<CostMetrics>("/api/v1/metrics/cost").then((r) => r.data);

export const getHealth = () =>
  api.get<{ status: string }>("/health").then((r) => r.data);

export const overrideCandidateScores = (jdId: string, candidateId: string, data: object) =>
  api.post(`/api/v1/jds/${jdId}/candidates/${candidateId}/override`, data).then((r) => r.data);

export const sendConversationMessage = (jdId: string, content: string) =>
  api.post(`/api/v1/jds/${jdId}/conversation`, { recruiter_id: "recruiter-1", content }).then((r) => r.data);

export const getConversation = (jdId: string) =>
  api.get(`/api/v1/jds/${jdId}/conversation`).then((r) => r.data);

export const sendOutreach = (candidateId: string, data: object) =>
  api.post(`/api/v1/candidates/${candidateId}/outreach`, data).then((r) => r.data);

export const getOutreachHistory = (candidateId: string) =>
  api.get(`/api/v1/candidates/${candidateId}/outreach`).then((r) => r.data);

export const getRetrievalMetrics = (jdId: string, k = 10) =>
  api.get(`/api/v1/eval/retrieval/${jdId}`, { params: { k } }).then((r) => r.data);

export const getScreeningMetrics = (jdId: string) =>
  api.get(`/api/v1/eval/screening/${jdId}`).then((r) => r.data);

export const getRankingMetrics = (jdId: string) =>
  api.get(`/api/v1/eval/ranking/${jdId}`).then((r) => r.data);

export const getWorkflowMetrics = () =>
  api.get("/api/v1/eval/workflow").then((r) => r.data);

export const getCostMetricsForJD = (jdId: string) =>
  api.get(`/api/v1/eval/cost/${jdId}`).then((r) => r.data);

export const getDeduplicationMetrics = (jdId: string) =>
  api.get(`/api/v1/eval/deduplication/${jdId}`).then((r) => r.data);