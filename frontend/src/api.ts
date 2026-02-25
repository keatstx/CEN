import type {
  AOPDefinition,
  ReadyResponse,
  Session,
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

export function createSession(
  module_name: string,
  context?: Record<string, unknown>,
): Promise<Session> {
  return request<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify({ module_name, context }),
  });
}

export function getSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}`);
}

export function executeWorkflow(
  input: WorkflowInput,
  sessionId?: string,
): Promise<WorkflowResult> {
  const url = sessionId ? `/execute?session_id=${sessionId}` : "/execute";
  return request<WorkflowResult>(url, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function approveSession(id: string): Promise<WorkflowResult> {
  return request<WorkflowResult>(`/sessions/${id}/approve`, {
    method: "POST",
  });
}

export function fetchModule(name: string): Promise<AOPDefinition> {
  return request<AOPDefinition>(`/modules/${name}`);
}

export function generateLLM(req: LLMGenerateRequest): Promise<LLMGenerateResponse> {
  return request<LLMGenerateResponse>("/tlm/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
