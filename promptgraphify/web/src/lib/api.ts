import type { AnalyzeResponse } from "./types";

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
}

async function parse(res: Response) {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(body?.error?.code ?? "http_error", body?.error?.message ?? res.statusText, res.status);
  }
  return body;
}

export async function analyze(files: { path: string; text: string }[], signal?: AbortSignal): Promise<AnalyzeResponse> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ files }),
    signal,
  });
  return parse(res);
}

export async function health(signal?: AbortSignal): Promise<HealthInfo> {
  return parse(await fetch("/api/health", { signal }));
}
