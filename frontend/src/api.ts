import type {
  ReadyResponse,
  WorkflowInput,
  WorkflowResult,
  LLMGenerateRequest,
  LLMGenerateResponse,
} from "./types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export function fetchReady(): Promise<ReadyResponse> {
  return request<ReadyResponse>("/ready");
}

export function executeWorkflow(input: WorkflowInput): Promise<WorkflowResult> {
  return request<WorkflowResult>("/execute", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function generateLLM(req: LLMGenerateRequest): Promise<LLMGenerateResponse> {
  return request<LLMGenerateResponse>("/tlm/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
