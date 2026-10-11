import type { AnalyzeResponse, QueryResult, QuerySpec } from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface HealthInfo {
  status: string;
  version: string;
  schema_version: string;
  llm_enabled: boolean;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_endpoint?: string | null;
}

async function parse(res: Response) {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(body?.error?.code ?? "http_error", body?.error?.message ?? res.statusText, res.status);
  }
  return body;
}

export async function analyze(
  files: { path: string; text: string }[],
  signal?: AbortSignal,
  layerB = false,
): Promise<AnalyzeResponse> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ files, layer_b: layerB }),
    signal,
  });
  return parse(res);
}

export async function health(signal?: AbortSignal): Promise<HealthInfo> {
  return parse(await fetch("/api/health", { signal }));
}

export async function listQueries(signal?: AbortSignal): Promise<QuerySpec[]> {
  return parse(await fetch("/api/queries", { signal }));
}

export async function runQuery(graphId: string, name: string, params: Record<string, string>, signal?: AbortSignal): Promise<QueryResult> {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""));
  return parse(await fetch(`/api/graph/${encodeURIComponent(graphId)}/query/${encodeURIComponent(name)}?${qs}`, { signal }));
}
