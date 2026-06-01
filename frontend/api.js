import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

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

export const listCandidates = (jdId, status) =>
  api
    .get(`/api/v1/jds/${jdId}/candidates`, { params: status ? { status } : {} })
    .then((r) => r.data);

export const getCandidate = (candidateId) =>
  api.get(`/api/v1/candidates/${candidateId}`).then((r) => r.data);

export const getCostMetrics = () =>
  api.get("/api/v1/metrics/cost").then((r) => r.data);

export const getHealth = () => api.get("/health").then((r) => r.data);
