import type {
  AOPDefinition,
  Project,
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

// ── Cases (canonical name; /sessions remains as a legacy alias) ──

export function createCase(
  module_name: string,
  options?: {
    context?: Record<string, unknown>;
    name?: string;
    project_id?: string;
  },
): Promise<Session> {
  return request<Session>("/cases", {
    method: "POST",
    body: JSON.stringify({
      module_name,
      context: options?.context,
      name: options?.name,
      project_id: options?.project_id,
    }),
  });
}

export function getCase(id: string): Promise<Session> {
  return request<Session>(`/cases/${id}`);
}

export function listCases(filters?: {
  module_name?: string;
  project_id?: string;
  limit?: number;
}): Promise<Session[]> {
  const params = new URLSearchParams();
  if (filters?.module_name) params.set("module_name", filters.module_name);
  if (filters?.project_id) params.set("project_id", filters.project_id);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return request<Session[]>(`/cases${qs ? `?${qs}` : ""}`);
}

export function patchCase(
  id: string,
  body: { name?: string; context?: Record<string, unknown> },
): Promise<Session> {
  return request<Session>(`/cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function provideInput(
  id: string,
  inputs: Record<string, unknown>,
): Promise<WorkflowResult> {
  return request<WorkflowResult>(`/cases/${id}/provide_input`, {
    method: "POST",
    body: JSON.stringify({ inputs }),
  });
}

// Legacy aliases retained for now — will be removed once App.tsx
// migrates fully to the case-named methods.
export const createSession = createCase;
export const getSession = getCase;

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
  return request<WorkflowResult>(`/cases/${id}/approve`, {
    method: "POST",
  });
}

// ── Projects ──

export function listProjects(limit = 50): Promise<Project[]> {
  return request<Project[]>(`/projects?limit=${limit}`);
}

export function createProject(
  name: string,
  description = "",
): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export function patchProject(
  id: string,
  body: { name?: string; description?: string },
): Promise<Project> {
  return request<Project>(`/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
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
