# CEN — Community Equity Navigators

AI Concierge platform for No Surprises Act compliance and patient financial advocacy. Executes AOP/DAG workflows that guide patients (or navigators acting on their behalf) through charity care, benefits enrollment, insurance appeals, debt cancellation, and community resource navigation. Designed to lighten the cognitive load on community equity navigators while producing a defensible audit trail for every patient outcome.

**Repo**: https://github.com/keatstx/CEN | **Deploy**: Render (single Docker service, FastAPI serves the built frontend)

---

## 1. Product Vision

These tenets govern every feature, design decision, and architectural choice. They are requirements, not aspirations.

1. **AI-assisted navigation, not AI-driven decisions** — AI removes drudgery (form prep, denial parsing, plain-language explanations) but every consequential action (appeal filing, debt cancellation request, benefit application) flows through an explicit `APPROVAL` gate. Navigators and patients stay in the loop.
2. **Declarative workflows over hardcoded logic** — Every patient journey is an AOP/DAG (Action/Operation/Procedure) JSON file. Business logic lives as data, not as if/else chains. Changing a workflow does not require a code change.
3. **Audit trail as a feature** — Every node execution, user input, file upload, approval, and concierge interaction is recorded in an append-only audit store with a verification chain. The audit is the compliance backbone, not an afterthought.
4. **Privacy-first by construction** — Patient data is PHI. PII scrubbing runs *before* any prompt assembly, before any telemetry emission, and before any audit persistence. There is no path from raw context to a third party that does not go through the scrubber.
5. **Plain language always** — Users (patients and front-line navigators) are not insurance experts, not lawyers, not engineers. Every label, error message, status, and concierge response speaks at an 8th-grade reading level. No HTTP codes, no enum names, no internal IDs surfaced to users.
6. **One workflow, one record, one truth** — A patient's case is one cohesive record across modules. Demographics entered once, files uploaded once, history visible across runs. No duplicate data entry.
7. **Idempotent resumability** — Workflows pause for input, approval, and external events. Resuming a paused workflow MUST NOT re-execute side-effecting nodes. Cached node outputs are part of session state.
8. **Provenance on every AI output** — Every LLM-generated draft, summary, or classification is tagged with model, prompt version, and timestamp. Outputs are never passed off as authoritative without a confidence indicator and source links where applicable.
9. **Stakeholder-appropriate language** — Patient-facing UI uses patient language. Navigator-facing UI may surface more detail (case ID, audit access, supervisor escalation). The same data, two presentations.

---

## 2. Tech Stack & Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| API | FastAPI (Python 3.9+) | Async-first |
| Database | SQLite via `aiosqlite` | Single-writer; plan to migrate to Postgres at multi-user scale |
| Workflow Engine | NetworkX DAG execution | Custom layered executor on top of `networkx` |
| LLM | Pluggable (`mock` / `gguf` / OpenAI-compatible API) | See LLM Backends below |
| Privacy | PII scrubbing (regex / Presidio) | Runs before audit, telemetry, and LLM calls |
| Logging | structlog | Console or JSON renderer |
| Frontend | React + Vite + TypeScript + Tailwind | Single-page app served by FastAPI in production |
| Deploy | Render (single Docker service) | `render.yaml` + `Dockerfile` at repo root |

### LLM Backends

**CEN ships with three backends; the active one is selected via `CEN_LLM_BACKEND`.**

| Backend | Use case | PHI safe? |
|---------|----------|-----------|
| `mock`  | Tests, dev without a model | Yes (no network) |
| `gguf`  | Local llama.cpp models | Yes (no network) |
| `api`   | OpenAI-compatible endpoint (Ollama, vLLM, hosted providers) | **Only with a signed BAA**. Default points to local Ollama. |

**Compliance rule**: any deployment that touches real patient data MUST use `mock`, `gguf`, or an `api` endpoint backed by a Business Associate Agreement. The `api` backend with no BAA is for development against synthetic data only. Document the active provider in the deployment record.

The LLM layer lives in `src/cen/llm/`. Implementations follow a single Protocol (`generate(prompt, max_tokens) -> str`). Wrap any new provider behind the protocol; never call third-party SDKs directly from routes or services.

### Database Environments

| Environment | Database | How to access |
|-------------|----------|---------------|
| **Local dev** | SQLite at `./data/cen.db` (or `:memory:` in tests) | `sqlite3 ./data/cen.db` |
| **Tests** | SQLite `:memory:` | Auto-managed by fixtures; no cleanup needed |
| **Render production** | SQLite on Render persistent disk | Avoid touching prod DB without explicit ask |

"Working locally" means the FastAPI app runs on `localhost:8000` against the local SQLite file. Do NOT touch production data unless explicitly instructed.

### Development Commands

```bash
# Backend
uvicorn cen.api.app:create_app --factory --reload --port 8000
pytest tests/ -v
pytest tests/core/test_engine.py -v          # single file
mypy src/cen                                 # if mypy is installed

# Frontend
cd frontend && npm run dev                   # vite dev server (port 5173)
cd frontend && npx tsc -b                    # type-check only
cd frontend && npm run build                 # production build
cd frontend && npm run lint
```

### Project Structure

```
src/cen/
├── api/                  # FastAPI app, routes, dependencies, middleware
│   ├── app.py            # create_app factory
│   └── routes/           # health, sessions, workflows, llm, modules
├── core/                 # Engine, models, session store, audit store, event bus
│   ├── engine.py         # NetworkX DAG executor with pause/resume
│   ├── models.py         # Pydantic models: Session, NodeType, SessionStatus, AOP*
│   ├── session_store.py  # aiosqlite-backed session CRUD
│   └── audit_store.py    # Append-only audit table with verification chain
├── llm/                  # Pluggable LLM backends (Protocol-based)
├── modules/              # AOP workflow definitions (JSON) loaded at startup
├── privacy/              # PII scrubber (regex or Presidio backend)
└── telemetry/            # AsyncEventBus, event types, handlers
tests/                    # Mirrored package layout
frontend/
├── src/
│   ├── components/       # DAGViewer, WorkflowForm, ResultPanel, ...
│   ├── api.ts            # Typed fetch client
│   └── types.ts          # Shared frontend types mirroring backend Pydantic
└── package.json
CEN_modules_v2/           # v2 AOP JSON workflow definitions
docs/                     # Architecture, deployment, runbooks (as added)
data/                     # SQLite db + uploaded artifacts (gitignored)
```

### Key Models

- **Session** *(aka Case — see §7 naming)* — A single execution of a workflow for one patient. Holds `context`, `executed_nodes`, `pending_node`, `approved_nodes`, `status`. Pinned to a specific module version at creation.
- **AOPDefinition** — A workflow JSON: `module_name`, `version`, `nodes`, `edges`. Loaded once at startup, immutable at runtime.
- **AOPNode** — One step. Type is `ACTION`, `CONDITION`, `HANDOFF`, or `APPROVAL`. Carries `metadata` (label, description, params, optional `input_schema`).
- **SessionStatus** — `ACTIVE`, `AWAITING_APPROVAL`, `AWAITING_INPUT` *(planned)*, `AWAITING_EXTERNAL` *(planned)*, `COMPLETED`, `FAILED`.
- **AuditEvent** — Append-only record of every node execution, input submission, upload, approval, and concierge query. Carries `event_type`, `payload` (PII-scrubbed), `actor`, `timestamp`, `prev_hash`, `hash` for tamper-evident chaining.

---

## 3. Architecture

**Authority**: when `docs/architecture.md` exists, it is the definitive architecture reference. Read and follow it for all work — planning, code changes, schema, API design. What follows below are the key principles; the full document (when authored) will hold detailed patterns, examples, and pre-flight checklists. Until then, this section is the source of truth.

### Core Principles

- **Layered**: Routes handle HTTP only. Services hold business logic. Stores handle persistence. Engine handles execution. Never mix layers — a route should never touch SQL, an engine should never touch HTTP.
- **Engine is pure** — `engine.py` takes a session + module + context, returns a result. No side effects outside the session/audit stores. Easy to test, easy to replay.
- **Workflows are data** — Adding a step, branch, or approval gate is a JSON edit, not a code change. If you find yourself adding `if module == "x"` in engine code, stop and reach for the AOP schema instead.
- **Single source of truth is the database**, but **events drive everything else** — telemetry, real-time updates, audit. Use `AsyncEventBus.emit(...)` for any state change worth observing.
- **For multi-file features**, use Plan Mode to explore the codebase and present the approach before writing code.

### Non-Negotiables

1. **PII Scrubbing on every external boundary** — Before audit persistence. Before telemetry emission. Before any prompt assembly. Before any LLM call (including the concierge). Before any error message that might escape to a log aggregator. Missing one path = a PHI leak. The scrubber lives in `src/cen/privacy/` — extend it, don't bypass it.
2. **Append-Only Audit Trail** — The audit store has no `update` or `delete` paths by design. Every state change emits an `AuditEvent`. The hash chain must remain unbroken. Right-to-delete is implemented as redaction (PII fields nulled, hash chain preserved), never as row deletion.
3. **Idempotent Engine Resumption** — A paused workflow that resumes MUST NOT re-execute side-effecting nodes. Use the `executed_nodes` skip-list and per-node output cache stored in `context["__node_outputs"]`. Any new ACTION node that calls an LLM, sends an email, files a request, or touches an external system must respect the cache.
4. **Module Version Pinning** — A session is pinned to the exact module version it was created against. Newer module versions do not affect in-flight sessions. Store `module_version` on the session at creation and load that version on resume.
5. **Declarative Workflows** — All branching, looping, and approval logic lives in AOP JSON. Engine code stays generic. The four node types (`ACTION`, `CONDITION`, `HANDOFF`, `APPROVAL`) are sufficient for every workflow shipped to date — extend the schema before adding a fifth.
6. **Confidence & Provenance on AI Output** — Every LLM output written to context should be tagged with `{model, prompt_version, timestamp, confidence?}`. Downstream nodes and the UI use this for "Verified by AI" vs "Needs Verification" affordances.
7. **API-First** — Every feature is a FastAPI route with a Pydantic request/response model. The frontend is one consumer. CLI/Postman/curl must be able to drive the same flow.
8. **Multi-Tenant Stub Now, Enforcement Later** — CEN currently runs single-operator (no auth). The data model carries `owner_id` (nullable) and every read/write goes through a service layer that takes an `owner_id` parameter. When auth lands, the enforcement is a one-line change in the service, not a schema migration.

### Public Endpoint Exception Pattern

CEN currently has no public/unauthenticated endpoints. When v2 introduces them (e.g., a patient self-service status link, a one-time secure document drop), they MUST follow this pattern:

- **Read-only by default.** Mutations on public endpoints require a one-shot, scoped, time-limited token.
- **Scoped to a single resource via unguessable token** (UUID v4 minimum, 128 bits of entropy). The token is the implicit access boundary.
- **No `owner_id` or operator info exposed** in the response.
- **No PII beyond the strict minimum** required for the patient to verify they're looking at the right thing.
- **Aggressive `Cache-Control` headers** for any file or document download.
- **Rate-limited** per token + IP.
- **Audited** — every public-endpoint hit emits an `AuditEvent` with `actor=public`.
- **Documented in this section** so the exception is visible at a glance.

### State Machine

```
                ┌─────────────────────────────┐
                │                             │
   ACTIVE ──► AWAITING_INPUT ──► ACTIVE       │
      │                              │        │
      ├──► AWAITING_APPROVAL ──────► │        │
      │                              │        │
      ├──► AWAITING_EXTERNAL ──────► │        │
      │                              │        │
      ├──► COMPLETED                 │        │
      │                              │        │
      └──► FAILED                    │        │
                                     ▼        │
                                  COMPLETED   │
```

`AWAITING_INPUT` and `AWAITING_EXTERNAL` are planned (see roadmap §10). The current implementation supports `ACTIVE → AWAITING_APPROVAL → ACTIVE → COMPLETED/FAILED` only.

### AOP Schema (Authoring Rules)

- Every node has a unique `snake_case` id.
- `CONDITION` nodes must have both `true_next` and `false_next` pointing to real node ids.
- Every non-terminal node has at least one outgoing edge.
- Every node must be reachable from a root node.
- Loops are allowed (negotiation rounds, retry pages) — the engine handles cycles.
- `metadata.input_schema` (planned) declares which context fields a node needs. The engine pauses with `AWAITING_INPUT` if a required field is missing.
- `metadata.params` is a free-form dict for prompt templates and ACTION configuration.
- Workflow JSON files live in `CEN_modules_v2/` for v2 modules and `src/cen/modules/` for any built-in defaults.

---

## 4. Engineering Standards

These apply to all new code and any existing code directly modified in a session. Do not refactor code outside the explicit scope of a task — flag violations in a summary instead.

### 4.1 Error Handling

- Every function that can fail must have explicit error handling. No bare `except:`.
- Use FastAPI exceptions (`HTTPException`, `RequestValidationError`) for HTTP-layer failures — not raw strings.
- Distinguish operational errors (expected — handle gracefully, return 4xx) from programmer errors (unexpected — let them surface as 500 with a sanitized message).
- Async operations must handle cancellation. External API calls (LLM, future webhooks) must have timeouts.
- Frontend: failed fetches must set explicit empty state with a retry affordance, not silently show nothing.
- **Never let an exception in event-bus emit block the user mutation.** Wrap `event_bus.emit(...)` in try/except with a `logger.warn(...)`; never re-throw.

### 4.2 Security & Privacy

- Treat all external input as untrusted. Validate via Pydantic at every API entry point.
- Never hardcode credentials, API keys, or secrets. Use `CEN_*` environment variables.
- All SQL goes through parameterized queries (aiosqlite supports this natively). No string interpolation in SQL.
- **Run the PII scrubber before**: audit persistence, telemetry emission, LLM prompt assembly (system prompt, user message, history), error logs that might contain context, exported audit trails.
- **No PII in logs.** Even at DEBUG. Log `session_id`, not patient name. Log `node_id`, not condition values that contain identifiers.
- Before any destructive operation: confirm scope, check dependencies, prefer redaction over deletion for audit-relevant data.
- File uploads (planned): server-side size cap, content-type whitelist (PDF, DOCX, JPG, PNG, HEIC, TIFF), magic-byte sniffing, sanitized filenames, encryption at rest, authenticated downloads.

### 4.3 Testing

- New functions and modified functions must have co-located tests (`tests/<package>/test_*.py`). Untouched legacy code does not require retroactive test coverage.
- Test coverage must include: happy path, documented failure modes, boundary values, and at least one adversarial input (oversized, missing required, cross-tenant when auth lands).
- Use AAA pattern: Arrange, Act, Assert. One logical assertion per test.
- Tests use `db_path=":memory:"` — no file cleanup needed.
- `pytest-asyncio` is configured with `asyncio_mode = "auto"` — async tests run automatically without decorators.
- API tests use `httpx.AsyncClient` with `ASGITransport` — no live server needed.
- Engine tests must verify both the result *and* the audit events emitted.
- **Tests must verify event emission and audit logging where applicable.** Any service that emits via `AsyncEventBus` or appends to the audit store must have a co-located test asserting the event was emitted with the expected type and payload (use a mock event bus / inspect the audit store directly).
- Run all tests: `pytest tests/ -v`. Single file: `pytest tests/core/test_engine.py -v`.

### 4.4 Performance

- Flag N+1 patterns and unbounded queries before implementing. SQLite is single-writer; long transactions block everything.
- Use pagination for any list endpoint that could return 100+ records (sessions, audit events). Cursor-based preferred over offset.
- Don't block the event loop with sync I/O inside async handlers. Use `aiosqlite`, `httpx.AsyncClient`, etc.
- LLM calls are slow (seconds). Surface them with explicit loading state in the UI. Future: streaming.
- Cache node outputs for engine resumability (see Non-Negotiable #3) — this is also the cheapest performance win for any re-execution path.

### 4.5 Observability

- All services use `structlog` with appropriate levels: DEBUG for tracing, INFO for lifecycle, WARN for recoverable anomalies, ERROR for failures.
- Never log PII, credentials, or raw context dicts. Use `session_id`, `node_id`, `event_type` as structured fields.
- New endpoints and event handlers should emit at least one DEBUG event for traceability.
- Metrics worth tracking (when telemetry expands): time-per-node, abandonment rate per node, concierge query rate, average tokens per LLM call, LLM cost per session.

### 4.6 Code Style

- Python: snake_case for functions and variables, PascalCase for classes, UPPER_SNAKE for constants. Use type hints everywhere — `mypy` should pass.
- TypeScript: camelCase for variables and functions, PascalCase for components and types. Strict mode is on; no `any` unless justified in a comment.
- Functions do one thing. Keep under 40 lines. Files under 300 lines. Flag violations in comments rather than refactoring outside scope.
- Comments explain *why*, not *what*. No restating obvious code.
- All code must pass `mypy src/cen` (when mypy is configured) and `cd frontend && npx tsc -b` before being considered complete.

### 4.7 Dependencies

- **Do not introduce new Python or npm dependencies without explicit justification** in the commit message or PR description, covering: (1) the use case, (2) why existing dependencies don't cover it, (3) maintenance status (last release < 12 months, active issue triage), (4) license (must be MIT, Apache-2.0, BSD, or MPL — flag anything else for review).
- Prefer actively maintained packages with permissive licenses and async support (Python) or strict TypeScript types (frontend).
- Wrap third-party libraries in a service or adapter layer — don't scatter raw SDK calls across modules. The `LLMBackend` Protocol pattern is the model to follow.
- Any change to `pyproject.toml` or `frontend/package.json` MUST include the justification above. A diff with new dependencies and no justification fails verification.

### 4.8 Claude Code Orchestration Rules

These are working-style rules for any agentic/automated session (not for humans reading this file).

- **Parallelism first** — when a task involves multi-file operations, evaluate file dependencies immediately. If reads/searches are independent, execute all `Read`/`Grep`/`Glob` calls in a single parallel block, not sequentially.
- **Strict write discipline** — before every file modification, perform a full `Read` of the target block. After writing, the harness tracks state automatically — do not re-read to "verify" unless a downstream tool reports an error.
- **Speculative search** — if a symbol or bug location is unknown, run a codebase-wide `Grep` for related patterns *before* asking the user for clarification. Asking should be the last resort, not the first.
- **Plan → Code → Verify → Fix → Report** — never report a task as done until verification passes per §6. If verification fails, fix autonomously; only escalate on architectural ambiguity.
- **Context discipline** — for sessions that exceed ~20 turns or accumulate large file reads, summarize the current architectural state and decisions into a working-memory note (in your reply, not as a file) so subsequent tool calls operate on a compact mental model.
- **Output discipline** — lead status updates with the high-level result. Implementation details go below or get truncated. Long verbatim file dumps in chat are noise; reference paths and line numbers instead.
- **Options before code** — for any non-trivial change, present 2-3 approach options before implementing. The user prefers to choose between approaches, not to receive a pre-chosen implementation.

### 4.9 Idempotency Discipline (CEN-specific)

- **Every ACTION node that could re-execute must be safe to re-execute** OR must store its output in `context["__node_outputs"][node_id]` and check the cache before re-running.
- New nodes that call LLMs, send messages, or touch external systems are non-idempotent by default. Treat them as such.
- Tests for non-idempotent nodes must cover the resume path: create session → execute partway → pause → resume → assert the side-effecting call was made *exactly once*.

---

## 5. Frontend Standards

**Goal**: a navigator or patient with no technical background can complete a workflow without instructions. Every interface decision serves a non-expert user, not a developer.

### Layout

- **Three-frame Executor pattern** *(target architecture)*: left = navigation + session list + stepper, middle = current step (form, upload, history), right = AI concierge chat. Today's Executor is two-frame; the rebuild is on the roadmap (§10).
- **DAG Viewer** is a separate tab with pan/zoom, TB/LR layout toggle, fullscreen mode, and hover tooltips. Renders any module from `/api/modules/{name}`.
- Main shell has tabs: **Executor**, **DAG Viewer**, **Audit**, and (planned) **SOP Upload**.

### UX Principles

- **Plain language always** — every label, status, and message is at an 8th-grade reading level. See language table below.
- **Action-oriented** — lead with "What needs your attention." Status badges with plain labels. Users know what to do next without instructions.
- **Reversible by default** — destructive actions get confirmation modals. Reversible actions get undo toasts. Never use a confirmation modal for a reversible action.
- **Progress is visible** — the stepper shows where you are in the workflow. Long operations (LLM calls) get explicit loading states with descriptive copy ("Generating your draft appeal letter, this may take 30 seconds…"), never an unannotated spinner.
- **Mobile-aware** — the three-frame layout collapses to single-column with bottom-sheet drawers on mobile. Field navigators may be in clinics with phones, not laptops.
- **Accessibility is not optional** — keyboard navigation across frames, ARIA landmarks, focus moves to the new step on advance, screen reader announces step changes. WCAG 2.1 AA target.

### Language Standards

User-facing strings must use plain navigator/patient language. Technical terms are forbidden in the UI.

| Do Not Use | Use Instead |
|------------|-------------|
| Session | Case |
| Node | Step |
| Context | Information |
| Execute / Run | Start / Continue |
| Status: ACTIVE | In progress |
| Status: AWAITING_APPROVAL | Waiting for your review |
| Status: AWAITING_INPUT | Needs your input |
| Status: COMPLETED | Done |
| Status: FAILED | Something went wrong |
| HANDOFF | Sent to specialist |
| APPROVAL | Review and approve |
| LLM / model | AI assistant |
| Module | Workflow |
| Final outcome | Result |
| HTTP 401 / 403 / 500 | Plain explanation + next step |

### Empty States

Every list, table, or workflow surface must have an explicit empty state with: (1) a plain-language explanation, (2) a clear call-to-action. Examples:
- *"No cases yet. Start your first workflow."* + button
- *"No documents uploaded for this step. Drag a file here or click to browse."*
- *"No questions yet. Ask the AI assistant anything about this step."*

### Error Messages

Every error surfaced to the user must include: (1) a plain-language description (no HTTP codes, no Python tracebacks), (2) a suggested next step. Examples:
- *"We couldn't save your information. Please check your connection and try again."*
- *"This file is larger than 25 MB. Try compressing it or uploading a smaller version."*

### AI Confidence Display

- Below-threshold confidence: yellow "Needs verification" badge with a link to the source (PDF page, condition node, etc.).
- High confidence: muted "Verified by AI" indicator.
- Processing states: descriptive copy from the engine (e.g. *"Reading your insurance card…"*), never a bare spinner.

### Concierge Guardrails

The right-frame AI concierge is a workflow assistant, **not** a doctor, lawyer, or financial advisor. The system prompt must:
- Establish the role: "You help users understand workflow steps. You are not a lawyer, doctor, or financial advisor."
- Refuse personalized legal/medical advice with a referral.
- Stay scoped to the current workflow and step context.
- Always cite the step it's referring to.
- The UI must show a visible disclaimer beneath the chat input.

### Planned Features (Do Not Implement Ad Hoc)

The following are roadmap features. Do not scaffold or implement outside an explicit task:
- SOP-to-DAG generator (upload SOP → AI generates AOP JSON).
- RAG-powered concierge with module-specific knowledge bases.
- Multi-language support.
- Patient self-service mode (vs current navigator-operated default).
- Project layer above sessions (one project per patient, multiple sessions per project).
- File upload + artifact storage.
- `AWAITING_INPUT` step-pause mechanism with `input_schema`.

---

## 6. Verification Process

**After EVERY code change, run ALL applicable checks below. Do not report work as done until each one is verified or explicitly marked N/A. No exceptions.**

The matrix below is the contract. Every dev session should produce a checklist showing the result of each check. If a check is N/A, say so and why.

### A. Build & Type Safety (always required)

| # | Check | Command | Pass criterion |
|---|-------|---------|----------------|
| A1 | Backend type check | `mypy src/cen` (if configured) | exit 0 |
| A2 | Backend tests for new/modified code | `pytest tests/<path> -v` | all pass |
| A3 | Full backend test suite | `pytest tests/ -v` | all pass (run when core/engine/store touched) |
| A4 | Frontend type check | `cd frontend && npx tsc -b` | exit 0 (run when frontend touched) |
| A5 | Frontend build | `cd frontend && npm run build` | exit 0 (run before deploy or when build config changes) |
| A6 | Frontend lint | `cd frontend && npm run lint` | exit 0 (when frontend touched) |

### B. Database & Schema (when models or queries change)

| # | Check | How to verify |
|---|-------|---------------|
| B1 | Migration applied (or schema-init function updated) for every new column or table | `sqlite3 ./data/cen.db ".schema <table>"` shows the new column |
| B2 | New columns are nullable OR carry a sensible default | `sqlite3 ./data/cen.db ".schema <table>"` — every new column is `NULL`-able or has `DEFAULT` |
| B3 | Test DB schema matches dev DB schema | `pytest tests/core/test_*store*.py -v` passes against `:memory:` AND `sqlite3 ./data/cen.db ".tables"` lists the new table |
| B4 | Indexes for common filter columns | `sqlite3 ./data/cen.db ".indexes <table>"` shows `idx_<table>_<col>` for any column used in `WHERE`/`ORDER BY` on hot paths |
| B5 | Foreign-key style references (`case_id`, `project_id`, `node_id`) are consistent across tables | `sqlite3 ./data/cen.db ".schema"` — types match across referencing tables |
| B6 | Backfill plan documented for any column that breaks existing rows | Comment in the migration file + commit message |
| B7 | Pydantic model in `models.py` matches the table schema field-by-field | Read both side-by-side |
| B8 | New table registered in any startup `_init_db` / migration runner so fresh installs get it | grep the init path |

### C. Privacy & PII (non-negotiable #1)

| # | Check | How to verify |
|---|-------|---------------|
| C1 | New code that touches `context` runs the PII scrubber before audit/log/LLM | grep for `scrub(` adjacent to every audit/log/llm call in the diff |
| C2 | New endpoints validate request bodies via Pydantic — no raw `dict` shoved into context | Read the route signature |
| C3 | New log statements never include patient name, DOB, SSN, address, raw context dicts | grep `logger.` in the diff |
| C4 | Concierge prompt assembly path runs scrubber on system prompt + user message + history | Read concierge service |
| C5 | New uploads enforce size cap and content-type whitelist server-side | Read upload route |

### D. Multi-Tenant Isolation Hooks (non-negotiable #8)

CEN currently runs single-operator with stub auth. Even so, every read/write goes through a service layer that takes an `owner_id` parameter. These checks ensure the **hooks** are in place so the future enforcement is a one-line change, not a schema migration.

| # | Check | How to verify |
|---|-------|---------------|
| D1 | Every new mutation accepts an `owner_id` parameter | grep service file — no mutation without an owner param |
| D2 | Every new query filters by `owner_id` (or joins via parent that does) | read each find/list/update path |
| D3 | New routes use the auth dependency (even if it returns a stub user today) | grep `Depends(get_current_user)` (or equivalent) on each new route |
| D4 | New tables that hold case/project data carry an `owner_id` column (nullable for v1) | `sqlite3 ./data/cen.db ".schema <table>"` |
| D5 | Cross-tenant negative test exists | a test that creates two stub users, asserts user B cannot read/update user A's resource — currently asserts the *path* is in place, will tighten when real auth lands |
| D6 | Public endpoints (when added) follow the §3 Public Endpoint Exception Pattern | inspect the route + this CLAUDE.md |

### E. Audit Trail (non-negotiable #2)

| # | Check | How to verify |
|---|-------|---------------|
| E1 | Every state change emits an `AuditEvent` via the audit store | grep `audit_store.append(` next to every save/delete in the diff |
| E2 | Audit payload is PII-scrubbed | inspect the payload assembly |
| E3 | Hash chain remains unbroken (no out-of-order writes, no skipped events) | inspect `audit_store.append` call sites |
| E4 | New event types are added to the canonical event-type list | grep the event type enum / constants |
| E5 | Live verification of persisted events | `sqlite3 ./data/cen.db "SELECT event_type FROM audit_events WHERE case_id='<uuid>' ORDER BY id"` returns the expected sequence |
| E6 | New event types are emitted via `AsyncEventBus.emit(...)` so telemetry handlers see them | grep event bus emit calls |
| E7 | Audit append failures wrapped in try/except — never block the user mutation | inspect call sites |

### F. Engine Resumability (non-negotiable #3)

| # | Check | How to verify |
|---|-------|---------------|
| F1 | Any new ACTION node with side effects checks `context["__node_outputs"][node_id]` before executing | read the node handler |
| F2 | Node outputs cached to context after execution | read the node handler |
| F3 | Resume test: pause mid-workflow, resume, assert the side-effecting call was made exactly once | dedicated test in `tests/core/test_engine.py` |
| F4 | New SessionStatus values added to the state machine diagram and to `models.py` enum | grep enum + this CLAUDE.md |
| F5 | Module version pinned on case creation | read create_case path |
| F6 | Case resume loads the pinned module version, not the current one | read the load path |

### G. API Surface & Frontend Integration

| # | Check | How to verify |
|---|-------|---------------|
| G1 | Live route mounts at expected path | `curl -o /dev/null -w "%{http_code}" http://localhost:8000/api/<route>` returns 200/422 (not 404) |
| G2 | OpenAPI schema regenerates cleanly | visit `http://localhost:8000/docs` |
| G3 | Frontend `api.ts` has a method per new endpoint | grep `frontend/src/api.ts` for the route fragment |
| G4 | Frontend interface matches backend Pydantic response field-by-field | Read `frontend/src/types.ts` AND the FastAPI response model; compare every field name + type |
| G5 | Frontend handler calls the new method | Search `frontend/src/components/**/*.tsx` for the api.ts method name |
| G6 | New tabs/pages are reachable from `App.tsx` navigation | walk the route from the top-level tab bar |
| G7 | CORS / dev proxy still works | browser console shows no CORS errors against `localhost:8000` |

### H. Live End-to-End Smoke Test (always required for new endpoints)

For every new mutation endpoint, run a real curl lifecycle against the running dev server. The cross-tenant negative test is mandatory even with stub auth — it locks the enforcement path in place for when real auth lands.

| # | Check | Command pattern |
|---|-------|-----------------|
| H1 | Login as stub operator, capture token | `curl -X POST http://localhost:8000/api/auth/login -d '{"password":"..."}' \| jq -r .access_token` |
| H2 | CREATE returns 200/201 with the entity | `curl -X POST http://localhost:8000/api/cases -H "Authorization: Bearer $T" -d '{...}'` |
| H3 | GET / LIST returns 200 with the new entity | `curl -H "Authorization: Bearer $T" http://localhost:8000/api/cases` |
| H4 | UPDATE / advance returns 200 with mutation applied | `curl -X POST http://localhost:8000/api/cases/<id>/provide_input -H "Authorization: Bearer $T" -d '...'` |
| H5 | DELETE / archive returns 200 and entity is gone (or redacted) | `curl -X DELETE http://localhost:8000/api/cases/<id> -H "Authorization: Bearer $T"` then re-LIST |
| H6 | Cross-tenant attempt with second stub operator returns 403/404 (never 200) | Register a second stub operator, retry H2-H5 against the first operator's resource |
| H7 | DB-level verification of mutations | `sqlite3 ./data/cen.db "SELECT status, executed_nodes FROM cases WHERE id='<uuid>'"` matches expectation |
| H8 | Audit verification | `sqlite3 ./data/cen.db "SELECT event_type FROM audit_events WHERE case_id='<id>' ORDER BY id"` shows expected sequence |

### I. Frontend UI Completeness (when web is touched)

| # | Check | How to verify |
|---|-------|---------------|
| I1 | Feature reachable from main navigation | walk the click path from the tab bar |
| I2 | All form fields round-trip (create → reload → fields preserved) | manual or e2e |
| I3 | Empty state present with explanation + CTA | render with no data; verify per Section 5 standards |
| I4 | Error states show plain language + next step (no HTTP codes) | trigger an error; verify message |
| I5 | Loading states are descriptive (no bare spinners on long operations) | trigger an LLM call; verify copy |
| I6 | Mobile responsive (no horizontal scroll, 44px tap targets) | DevTools mobile viewport |
| I7 | Language review — no jargon | scan strings against the Section 5 forbidden-terms table |
| I8 | Confirmation modals for destructive actions; toasts for reversible ones | per Section 5 |

### J. Test Coverage (per Section 4.3)

| # | Check | How to verify |
|---|-------|---------------|
| J1 | New service functions have a `test_*.py` co-located | `ls tests/<package>/test_*.py` |
| J2 | Tests cover happy path | a test asserting the expected return |
| J3 | Tests cover documented failure modes | one `pytest.raises(...)` per failure mode |
| J4 | Tests cover boundary values (empty context, max-length string, missing required field) | at least one boundary case per typed input |
| J5 | Tests cover at least one adversarial input (oversized payload, missing scrubber field, cross-tenant) | mandatory for every public endpoint |
| J6 | Tests verify event emission (per §4.3) | `assert mock_event_bus.emit.called_with(...)` or inspect audit store directly |
| J7 | Engine-related tests verify idempotency on resume (per §4.9) | dedicated resume test for non-idempotent nodes |

### K. Security & Hygiene

| # | Check | How to verify |
|---|-------|---------------|
| K1 | No secrets in code or commits | grep diff for `API_KEY`, `password`, `token` literals |
| K2 | All external input validated by Pydantic at the entry point | read each new route signature |
| K3 | No raw SQL string interpolation | grep for f-strings or `%` formatting in SQL |
| K4 | No PII / credentials in new logger calls | grep `logger.` in the diff |
| K5 | Destructive operations (DELETE, file remove) have explicit scope and dependency check | grep `delete(` / `os.remove(` |
| K6 | New dependencies justified per 4.7 | `pyproject.toml` / `package.json` diff is empty OR justification in commit message |

### L. Reporting

After running the above, the dev session report MUST include a table like:

```
| Check | Status |
|-------|--------|
| A1 mypy                          | ✅ |
| A2 pytest tests/core/            | ✅ 14 passed |
| A4 tsc -b                        | ✅ |
| C1 PII scrubber wired            | ✅ scrub() called before audit + LLM |
| D1 owner_id on every mutation    | ✅ |
| D5 cross-tenant negative test    | ✅ user B → user A resource = 403 |
| E1 audit emit on state change    | ✅ 4 events in chain |
| F3 resume idempotency test       | ✅ side-effect called exactly once |
| H1-H8 endpoint lifecycle         | ✅ login/create/list/update/delete/cross-tenant/db/audit |
```

If any row is ❌ or ⚠️, fix it before reporting "done". If any row is N/A, say why (e.g. *"I1-I8 N/A — backend-only change"*).

### Quick reference: when to skip what

- **Backend-only change**: skip I entirely; A4/A5 only if frontend imports backend-generated types.
- **Frontend-only change**: skip B/D/E/F/H entirely; still do A4/A5/A6 and G.
- **Schema-only change**: skip G/H/I; B, D, and E are mandatory.
- **Test-only change**: A2/A3 only.
- **Doc-only change**: skip everything except a sanity read of the doc.

---

## 7. Operational Rules

### Naming

- The codebase currently uses **`session`** to mean "one execution of a workflow." This collides with HTTP/auth session terminology and we are migrating to **`case`**. New code should use `case` where it does not break existing imports; existing `session` references stay until a coordinated rename. Document any partial-rename PRs in commit messages.

### Git

- **NEVER combine `cd` with `git` in a single compound command.** This triggers a "bare repository attack" approval prompt on this Windows machine. Always run `cd` and `git` as separate Bash tool calls.
- Never automatically commit. Only commit when the user explicitly requests.
- Use conventional commit format (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`).
- Include `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>` in commit messages.

### Deployments

CEN deploys to Render as a single Docker service that builds the frontend and serves it via FastAPI. See `Dockerfile` and `render.yaml`. Only deploy when the user explicitly requests.

Pre-deploy verification (in addition to §6 checks):
- `cd frontend && npm run build` — exit 0.
- `python -c "from cen.api.app import create_app; create_app()"` — no import errors.
- All migrations / schema-init paths idempotent (running twice does not break anything).

### Destructive Operations

Before ANY destructive operation (DELETE, DROP, removing files):
1. Confirm exact scope with the user.
2. Check dependencies (foreign-key references, in-flight sessions, audit constraints).
3. Use specific WHERE clauses — never delete-all when the user specified one.
4. For audit-relevant data, prefer redaction (null PII fields, preserve hash chain) over deletion.
5. Don't delete `data/uploads/`, `data/cen.db`, or other infrastructure paths the app needs.

### User-Facing Commands

The user runs commands in PowerShell on Windows. When providing terminal commands for the user to run locally:
- Use `Remove-Item -Recurse -Force` not `rm -rf`
- Use `cd C:\path\to\dir` with backslashes
- Use `$env:VAR = "value"` not `export VAR=value`
- The Bash tool used by Claude Code internally accepts Unix syntax (it shells through Git Bash). Commands given **to the user** must be PowerShell.

### Autonomous Behavior

- Follow the loop: **Plan → Code → Verify → Fix → Report**. Do not report back until all verification passes.
- If a build or test fails, investigate and fix autonomously. Only ask the user when there's an architectural ambiguity or a decision with multiple valid approaches.
- For multi-file features, use Plan Mode first.
- Present **options before code** for any non-trivial change. The user prefers to choose between approaches before implementation begins.

---

## 8. Common Pitfalls

1. **SQLite single-writer**: long-running write transactions block all other writes. Keep transactions short. For batch operations, prefer many small commits over one big one.
2. **`aiosqlite` is not magic**: it serializes writes to a single thread internally. Don't expect parallelism on the write path.
3. **AOP JSON loaded at startup**: changing a module file requires a server restart. The dev server with `--reload` handles this; production does not.
4. **`networkx` cycle handling**: the engine supports loops (negotiation rounds), but the topological layout in `DAGViewer.tsx` does not — it assigns layers via Kahn's algorithm and treats cycles by best-effort layering. If you add deeply nested cycles, the visual will get weird before the engine does.
5. **PII scrubber is regex by default**: the regex backend covers common PII (SSN, phone, email, MRN-ish patterns) but is not exhaustive. For real PHI, switch to `CEN_PII_BACKEND=presidio` and verify Presidio's spaCy model is installed.
6. **`mock` LLM backend in tests**: `mock` returns a deterministic canned response. Tests must not assume any specific phrasing — assert structure, not content.
7. **Re-execution duplicates side effects**: the engine's current resume model re-runs from the entry node with `approved_nodes` set. Any new ACTION node that calls an LLM or external API will re-fire on every resume **until the output cache (Non-Negotiable #3) is implemented**. Until then, prefer pure ACTION nodes or guard side effects manually.
8. **FastAPI `BackgroundTasks` runs after the response**: don't use them for anything that affects the response payload. Use them for telemetry, audit, and notifications.
9. **Pydantic v2 behavior**: model field aliases, `.model_dump()` instead of `.dict()`, validators are now `@field_validator`. Don't mix v1 patterns with v2 code.
10. **Frontend build artifacts are gitignored**: `frontend/dist/` and `frontend/.vite/` should never be committed. The Dockerfile builds them at deploy time.

---

## 9. Reference Documentation

| Document | Path |
|----------|------|
| Project README | `README.md` |
| MVP Development Guide | `MVP Development Guide_AI Concierge for Community Equity Navigators.md` |
| Original prompt / scope | `Prompt.md` |
| AOP module v2 definitions | `CEN_modules_v2/` |
| Render deployment config | `render.yaml`, `Dockerfile` |
| Local LLM setup | `local_llm/` |
| Architecture docs (when added) | `docs/architecture.md` |
| Deployment runbook (when added) | `docs/deployment.md` |
| State machine reference (when added) | `docs/state-machine.md` |

### Skills

| Skill | Purpose |
|-------|---------|
| `/commit` | Stage and commit with conventional message |
| `/summarize` | Summarize session work and decisions |

### Subagents

- **Explore**: Search codebase, find patterns, understand existing code (use for >3 file investigations).
- **Plan**: Features touching 3+ files or complex architecture.
- **general-purpose**: Multi-step research, keyword searches across the codebase.

---

## 10. Roadmap (active design questions)

These are the open architectural decisions we're working through. They directly affect what code gets written next. Keep this section updated as decisions land.

### Tier 1 — Blocking decisions

- **Project layer above sessions**: do we introduce a `Project` (one per patient, multiple sessions per project) before the new Executor is built? Affects schema fundamentally.
- **Patient self-service vs navigator-operated**: which user is the v1 target? Affects every UX decision.
- **Real PHI vs synthetic-only for v1**: determines whether file encryption at rest, BAA-backed LLM, and auth must land before the new features.
- **Auth strategy**: build minimal operator login now, or guarantee dev-only deployment with no real PHI until a dedicated auth milestone?
- **Engine idempotency strategy**: skip-list with cached node outputs (recommended), per-node snapshot, or mark-idempotent flag?
- **Session → Case rename**: do we do a coordinated rename now, or defer until the new Executor lands?

### Tier 2 — Design in progress

- **Three-frame Executor rebuild**: left = nav + session list + stepper, middle = step interaction (form, upload, history), right = AI concierge.
- **Step-pause mechanism**: declarative `input_schema` per node + auto-pause on CONDITION nodes whose `condition_field` is missing from context.
- **File upload + artifact storage**: server-side validation, encryption at rest, audit on every upload/download.
- **AI concierge v1**: stateless prompt builder with session context, PII scrubber on the assembly path, scope guardrails, conversation history truncation. RAG comes later.
- **Schema migration framework**: introduce alembic (or equivalent) before the next round of schema changes.
- **Module version pinning** on session creation.
- **Optimistic concurrency** (`version` column) on Session updates.

### Tier 3 — Backlog

- SOP-to-DAG generator (upload SOP, AI extracts AOP JSON, user reviews and saves).
- RAG-powered concierge with module-specific knowledge bases.
- Multi-language support (system prompt + UI strings).
- Mobile responsive collapse of the three-frame Executor.
- Background worker for retention enforcement, abandoned-session reminders, audit chain verification.
- Postgres migration when SQLite becomes a bottleneck.
- Session forking / templates.
- Printable case dossier export.
