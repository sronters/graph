import type { AnalysisJob, Dataset, Experiment, Finding, Identity, Page } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json();
  if (!response.ok) {
    throw new ApiError(body.error?.message ?? "GraphTrust API request failed", response.status);
  }
  return body as T;
}

export const api = {
  datasets: () => request<Page<Dataset>>("/api/v1/datasets?page_size=200"),
  createAnalysis: (datasetId: string) =>
    request<AnalysisJob>("/api/v1/analyses", {
      method: "POST",
      body: JSON.stringify({
        dataset_id: datasetId,
        methods: ["direct", "privileged", "untyped", "native_scope", "graphtrust"],
      }),
    }),
  analysis: (analysisId: string) => request<AnalysisJob>(`/api/v1/analyses/${analysisId}`),
  summary: (analysisId: string) =>
    request<Record<string, unknown>>(`/api/v1/analyses/${analysisId}/summary`),
  identities: (analysisId: string, query = "") =>
    request<Page<Identity>>(
      `/api/v1/analyses/${analysisId}/identities?page_size=200&search=${encodeURIComponent(query)}`,
    ),
  identity: (analysisId: string, nodeId: string) =>
    request<{ scores: Identity[]; top_paths: Finding[] }>(
      `/api/v1/analyses/${analysisId}/identities/${encodeURIComponent(nodeId)}`,
    ),
  paths: (analysisId: string) =>
    request<Page<Finding>>(`/api/v1/analyses/${analysisId}/paths?page_size=200`),
  remediations: (analysisId: string, solver: string, target: number) =>
    request<{ items: Record<string, unknown>[]; recommendation_only: boolean }>(
      `/api/v1/analyses/${analysisId}/remediations`,
      { method: "POST", body: JSON.stringify({ solvers: [solver], targets: [target] }) },
    ),
  experiments: () => request<Page<Experiment>>("/api/v1/experiments?page_size=200"),
  experimentMetrics: (runId: string) =>
    request<{ detection: Record<string, number> }>(`/api/v1/experiments/${runId}/metrics`),
  experimentArtifacts: (runId: string) =>
    request<{ artifacts: { name: string; size_bytes: number; sha256: string }[] }>(
      `/api/v1/experiments/${runId}/artifacts`,
    ),
};
