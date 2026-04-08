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
    // FastAPI default error key is `detail`; our custom error handlers
    // sometimes use `error`. Try both before falling back to a generic.
    const message =
      body.detail ??
      body.error ??
      body.message ??
      `Request failed: ${res.status}`;
    const err = new Error(typeof message === "string" ? message : JSON.stringify(message));
    // Tag the error with the HTTP status so callers can distinguish
    // 404 (stale id) from 409 (wrong state) etc.
    (err as Error & { status?: number }).status = res.status;
    throw err;
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

export async function deleteCase(id: string): Promise<void> {
  const res = await fetch(`/cases/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Delete failed: ${res.status}`);
  }
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

// ── Concierge ──

export interface ConciergeCitation {
  faq_id: string;
  question: string;
  score: number;
}

export interface ConciergeResponse {
  answer: string;
  mode: "lookup" | "format" | "guardrail";
  citations: ConciergeCitation[];
}

export interface FAQ {
  id: string;
  module_name: string | null;
  project_id: string | null;
  question: string;
  answer: string;
  source_filename: string;
  owner_id: string | null;
  created_at: string;
}

export function askConcierge(
  question: string,
  caseId?: string,
): Promise<ConciergeResponse> {
  return request<ConciergeResponse>("/concierge/ask", {
    method: "POST",
    body: JSON.stringify({ question, case_id: caseId }),
  });
}

export function listFAQs(filters?: {
  module_name?: string;
  project_id?: string;
}): Promise<FAQ[]> {
  const params = new URLSearchParams();
  if (filters?.module_name) params.set("module_name", filters.module_name);
  if (filters?.project_id) params.set("project_id", filters.project_id);
  const qs = params.toString();
  return request<FAQ[]>(`/faqs${qs ? `?${qs}` : ""}`);
}

export function createFAQ(body: {
  question: string;
  answer: string;
  module_name?: string;
  project_id?: string;
}): Promise<FAQ> {
  return request<FAQ>("/faqs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteFAQ(id: string): Promise<void> {
  return fetch(`/faqs/${id}`, { method: "DELETE" }).then(() => undefined);
}

// ── Artifacts (file uploads) ──

export interface Artifact {
  id: string;
  case_id: string;
  project_id: string | null;
  node_id: string | null;
  filename: string;
  content_type: string;
  size: number;
  storage_key: string;
  owner_id: string | null;
  uploaded_at: string;
}

export async function uploadArtifact(
  caseId: string,
  file: File,
  nodeId?: string,
): Promise<Artifact> {
  const form = new FormData();
  form.append("file", file);
  if (nodeId) form.append("node_id", nodeId);
  const res = await fetch(`/cases/${caseId}/artifacts`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? body.error ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}

export function listArtifacts(caseId: string): Promise<Artifact[]> {
  return request<Artifact[]>(`/cases/${caseId}/artifacts`);
}

export function artifactDownloadUrl(artifactId: string): string {
  return `/artifacts/${artifactId}`;
}

export async function deleteArtifact(artifactId: string): Promise<void> {
  const res = await fetch(`/artifacts/${artifactId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Delete failed: ${res.status}`);
  }
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
