# CEN — Community Equity Navigators

AI Concierge platform for No Surprises Act compliance and patient financial advocacy. Executes AOP/DAG workflows that guide patients (or navigators acting on their behalf) through charity care, benefits enrollment, insurance appeals, debt cancellation, and community resource navigation. Lightens cognitive load on navigators and produces a defensible audit trail for every outcome.

**Repo**: https://github.com/keatstx/CEN | **Live**: https://cen-48pm.onrender.com | **Deploy**: Render (single Docker service, FastAPI serves the built frontend)

---

## 1. Product Vision

Requirements, not aspirations. Every feature must serve these:

1. **Navigator co-pilot, not autopilot** — Every consequential action (appeal filing, debt cancellation request, benefit application) flows through an explicit `APPROVAL` gate. AI removes drudgery; navigators stay in the loop. Patients consume the output; navigators are the v1 operator.
2. **Conversational throughout** — The right-panel concierge is not a help widget. It reads where the user is in the workflow, pulls from the project's FAQ library, the case context, and the active SOP, and speaks at an 8th-grade reading level. Every response is grounded in a citable source — no ungrounded synthesis, ever.
3. **Workflows are data, authored by humans** — Patient journeys are AOP/DAG JSON. Navigators (or supervisors) author them by uploading SOPs that the system extracts into reviewable drafts. Business logic never lives in code as if/else chains.
4. **Audit trail is the compliance backbone** — Every node execution, user input, file upload, approval, concierge turn, and SOP promotion is recorded in an append-only audit store with a verification chain. Right-to-delete is implemented as redaction, never as row deletion.
5. **PHI compliance is non-negotiable infrastructure** — PII scrubbing runs before any prompt assembly, telemetry emission, or audit persistence. The `deployment_mode` + BAA gate prevents real PHI from reaching a non-BAA'd LLM provider. Compliance is enforced in code, not policy.
6. **Plain language always** — 8th-grade reading level for navigators and patients alike. No HTTP codes, enum names, internal IDs, or model names surfaced in the UI. Errors lead with what to do next, not what went wrong.
7. **One patient, one record, one truth** — A patient's case is one cohesive record across modules. Demographics entered once, files uploaded once, history visible across runs. The Project layer is the unit of identity; Sessions (Cases) are executions under it.
8. **Idempotent resumability** — Workflows pause for input, approval, and external events. Resuming a paused workflow MUST NOT re-execute side-effecting nodes. The output cache is part of session state and the resume path is tested for every non-idempotent ACTION node.
9. **Provenance on every AI output** — Every concierge reply, extracted SOP draft, or LLM-generated content carries source pointers (`faq_id`, `sop_id`, `node_id`) and a kind tag. The UI surfaces sources inline so navigators can verify before acting on AI output.
10. **Multi-source RAG over fragmented data** — The concierge fuses FAQ library, SOP library, current workflow step, and case context into one retrieval. Each source is owner-scoped and project-scoped; cross-tenant leakage is impossible by construction. New data sources slot in behind the same retriever Protocol.

---

## 2. Critical Environment Facts

These are non-obvious and cause bugs when forgotten.

### LLM Backends — selected via `CEN_LLM_BACKEND`

| Backend | Use case | PHI safe? |
|---------|----------|-----------|
| `mock`  | Tests, dev without a model | Yes (no network) |
| `gguf`  | Local llama.cpp models | Yes (no network) |
| `api`   | OpenAI-compatible endpoint (Ollama, vLLM, hosted) | **Only with a signed BAA**. Default = local Ollama. |

Compliance rule: any deployment touching real patient data MUST use `mock`, `gguf`, or `api` backed by a BAA. The LLM layer lives in `src/cen/llm/`; new providers go behind the `LLMBackend` Protocol — never call third-party SDKs from routes/services.

### Database Environments

| Environment | Database | Access |
|-------------|----------|--------|
| Local dev | SQLite at `./data/cen.db` | `sqlite3 ./data/cen.db` |
| Tests | SQLite `:memory:` | Auto-managed by fixtures |
| Render production | SQLite on Render persistent disk | Avoid touching without explicit ask |

"Working locally" = FastAPI on `localhost:8000` against local SQLite. Do NOT touch production data unless explicitly asked.

### Other Project-Specific Gotchas

- **AOP JSON loaded at startup** — module file changes need a server restart. `--reload` handles this in dev; production does not.
- **SQLite single-writer** — long write transactions block all other writes. Keep transactions short.
- **`aiosqlite` is not parallel** — serializes writes internally. Don't expect parallelism on the write path.
- **Re-execution + idempotency** — engine re-runs from the entry node on resume; the `context["__node_outputs"]` cache (shipped) makes each node replay instead of re-firing, so LLM/external side effects happen exactly once. Inside a bounded loop the cache key is namespaced per iteration (once per pass). New ACTION nodes still must respect the cache to stay idempotent.
- **`mock` LLM returns canned responses** — assert structure, not content.
- **PII scrubber is regex by default** — covers common patterns, not exhaustive. For real PHI, set `CEN_PII_BACKEND=presidio` and verify spaCy model installed.
- **Pydantic v2** — `.model_dump()` not `.dict()`, `@field_validator` not `@validator`. Don't mix v1 patterns.
- **`networkx` cycles** — the engine runs *bounded loop regions* (LDCG): a `loop_back` edge + a `LoopSpec` on the entry, condensed to a super-node so the topological walk still works. Unannotated cycles are still rejected at load. `DAGViewer.tsx` (Kahn's topological layout) does **not** render loops yet — a loop-bearing workflow shows its skeleton, and the loop_back edge renders oddly.
- **`BackgroundTasks` runs after the response** — never use for anything affecting the response payload.
- **Frontend build artifacts gitignored** — `frontend/dist/` and `frontend/.vite/` never committed. Dockerfile builds at deploy time.

### Development Commands

```bash
# Backend
uvicorn cen.api.app:create_app --factory --reload --port 8000
pytest tests/ -v
mypy src/cen

# Frontend
cd frontend && npm run dev          # vite dev (port 5173)
cd frontend && npx tsc -b           # type-check
cd frontend && npm run build
cd frontend && npm run lint
```

### Project Structure

```
src/cen/
├── api/          # FastAPI app, routes, deps, middleware
├── core/         # engine.py, models.py, session_store.py, audit_store.py
├── llm/          # Pluggable backends (Protocol-based)
├── modules/      # Built-in AOP definitions
├── privacy/      # PII scrubber (regex / Presidio)
└── telemetry/    # AsyncEventBus, event types, handlers
tests/                    # Mirrored package layout
frontend/src/             # React + Vite + TS + Tailwind
CEN_modules_v2/           # v2 AOP JSON workflows
data/                     # SQLite + uploads (gitignored)
```

### Key Models

- **Session** *(aka Case — see §7 naming)* — One execution of a workflow for one patient. Holds `context`, `executed_nodes`, `pending_node`, `approved_nodes`, `status`. Pinned to a module version at creation.
- **AOPDefinition** — Workflow JSON: `module_name`, `version`, `nodes`, `edges`. Loaded at startup, immutable at runtime.
- **AOPNode** — Type is `ACTION`, `CONDITION`, `HANDOFF`, or `APPROVAL`. Carries `metadata` (label, description, params, optional `input_schema`).
- **SessionStatus** — `ACTIVE`, `AWAITING_APPROVAL`, `AWAITING_INPUT` *(planned)*, `AWAITING_EXTERNAL` *(planned)*, `COMPLETED`, `FAILED`.
- **AuditEvent** — Append-only with `event_type`, PII-scrubbed `payload`, `actor`, `timestamp`, `prev_hash`, `hash`.

---

## 3. Architecture

**Authority**: when `docs/architecture.md` exists, it is definitive. Until then, this section is the source of truth.

### Non-Negotiables

1. **PII Scrubbing on every external boundary** — Before audit, telemetry, prompt assembly (system + user + history), error logs, exported data. The scrubber lives in `src/cen/privacy/` — extend it, don't bypass it.
2. **Append-Only Audit Trail** — No update/delete paths. Every state change emits an `AuditEvent`. Hash chain unbroken. Right-to-delete = redaction (PII nulled, chain preserved).
3. **Idempotent Engine Resumption** — Side-effecting nodes use `executed_nodes` skip-list and per-node cache `context["__node_outputs"]`. Any new ACTION node that calls an LLM, sends an email, or files a request must respect the cache.
4. **Module Version Pinning** — Session pinned to module version at creation. Newer versions don't affect in-flight sessions.
5. **Declarative Workflows** — Branching/looping/approval logic lives in AOP JSON. The four node types remain sufficient: document generation is an ACTION subtype (`metadata.action_kind == "generate"`) and bounded loops are edge/metadata annotations (`loop_back` edge + `LoopSpec`), not a fifth node type. Extend via metadata before adding a type.
6. **Confidence & Provenance** — Every LLM output tagged with `{model, prompt_version, timestamp, confidence?}`. UI uses for "Verified by AI" vs "Needs Verification" affordances.
7. **API-First** — Every feature is a FastAPI route with Pydantic models. Frontend is one consumer; CLI/curl drives the same flow.
8. **Multi-Tenant Stub Now, Enforcement Later** — `owner_id` (nullable) on every record. Reads/writes go through a service layer taking `owner_id`. When auth lands, enforcement is a one-line change.

### Layering

Routes handle HTTP only. Services hold business logic. Stores handle persistence. Engine handles execution. Never mix. Engine is pure: takes session + module + context, returns a result. No side effects outside session/audit stores.

### Public Endpoint Exception Pattern

CEN currently has no public/unauthenticated endpoints. When v2 introduces them, they MUST: be read-only by default (mutations need a one-shot scoped time-limited token), scope via unguessable token (UUID v4 minimum), expose no `owner_id`/operator info, expose no PII beyond strict minimum, set aggressive `Cache-Control` on file downloads, rate-limit per token+IP, audit every hit with `actor=public`, and be documented here.

### State Machine

Current: `ACTIVE → AWAITING_APPROVAL → ACTIVE → COMPLETED/FAILED`. Planned: `AWAITING_INPUT`, `AWAITING_EXTERNAL` (see §8).

### AOP Schema Rules

- Unique `snake_case` node ids.
- `CONDITION` nodes need both `true_next` and `false_next` pointing to real ids.
- Every non-terminal node has at least one outgoing edge; every node reachable from a root.
- Loops allowed as **bounded regions** (negotiation rounds, retry): a `loop_back` edge (exit→entry) + a `LoopSpec` on the entry (`exit_condition_field`, `max_iterations`, `on_limit_next` → an APPROVAL/HANDOFF gate). Unannotated cycles are rejected at load. Loop bodies must not contain branching CONDITION nodes (the controller makes the loop decision).
- `metadata.input_schema` declares required context fields — engine pauses with `AWAITING_INPUT` if missing.
- Workflow JSON lives in `CEN_modules_v2/` (v2) and `src/cen/modules/` (built-in defaults).

---

## 4. Engineering Standards

Apply to new code and modified code. Don't refactor out-of-scope code — flag it instead.

### 4.1 Error Handling

- FastAPI exceptions (`HTTPException`, `RequestValidationError`) — not raw strings.
- No bare `except:`. Distinguish operational (4xx) from programmer errors (sanitized 500).
- External calls must have timeouts. Async ops handle cancellation.
- Frontend: failed fetches set explicit empty state with retry, never silently show nothing.
- **Never let an exception in `event_bus.emit(...)` block the user mutation.** Wrap in try/except + `logger.warn`; never re-throw.

### 4.2 Security & Privacy

- All external input untrusted — Pydantic-validate at every entry.
- No hardcoded secrets — use `CEN_*` env vars.
- All SQL parameterized via aiosqlite. No string interpolation.
- **Run the PII scrubber before**: audit, telemetry, LLM prompt assembly (system + user + history), error logs that may leak context, exported audit.
- **No PII in logs, even DEBUG.** Log `session_id` not patient name; log `node_id` not raw condition values.
- File uploads (planned): server-side size cap, content-type whitelist (PDF/DOCX/JPG/PNG/HEIC/TIFF), magic-byte sniff, sanitized filenames, encryption at rest, authenticated downloads.

### 4.3 Testing

- New/modified functions need co-located `tests/<package>/test_*.py`. Untouched legacy exempt.
- Coverage: happy path, documented failure modes, boundary values, at least one adversarial input (oversized, missing required, cross-tenant when auth lands).
- AAA pattern, one logical assertion per test.
- Tests use `db_path=":memory:"`. `pytest-asyncio` is `auto` mode. API tests use `httpx.AsyncClient` with `ASGITransport`.
- Engine tests verify result *and* audit events.
- Any service emitting via `AsyncEventBus` or appending to audit needs a co-located test asserting the event/payload.
- Run: `pytest tests/ -v` or `pytest tests/core/test_engine.py -v`.

### 4.4 Performance

- Flag N+1 and unbounded queries before implementing. SQLite is single-writer.
- Paginate any list that could return 100+ records (cursor-based preferred).
- Don't block the event loop with sync I/O in async handlers — use `aiosqlite`, `httpx.AsyncClient`.
- Surface LLM calls with explicit loading state. Cache node outputs (Non-Negotiable #3).

### 4.5 Observability

- `structlog` only — never `print` or `logging` directly. Levels: DEBUG (tracing), INFO (lifecycle), WARN (recoverable), ERROR (failures).
- Never log PII, credentials, or raw context dicts. Use `session_id`, `node_id`, `event_type` as structured fields.
- New endpoints emit at least one DEBUG event for traceability.

### 4.6 Code Style

- Python: snake_case fns/vars, PascalCase classes, UPPER_SNAKE constants. Type hints everywhere — `mypy src/cen` must pass.
- TypeScript: camelCase, PascalCase components/types. Strict mode; no `any` without justification.
- Functions one thing, under 40 lines. Files under 300 lines. Flag violations in comments — don't refactor out of scope.
- Comments explain *why*, not *what*.

### 4.7 Dependencies

- New deps require commit-message justification: use case, why existing deps don't cover, maintenance status (last release < 12 months), license (MIT/Apache/BSD/MPL).
- Wrap third-party libs in a service/adapter layer — the `LLMBackend` Protocol is the model.
- Diff with new deps and no justification fails verification.

### 4.8 Idempotency Discipline (CEN-specific)

- Every ACTION node that could re-execute must be safe to re-execute OR store output in `context["__node_outputs"][node_id]` and check the cache before re-running.
- Nodes that call LLMs, send messages, or touch external systems are non-idempotent by default.
- Tests for non-idempotent nodes must cover resume: create → execute partway → pause → resume → assert side-effecting call made *exactly once*.

### 4.9 File Size — Don't Grow Monoliths

**Before editing any file, check its line count.** If already over 300, DO NOT append — extract the addition into a dedicated module/component file and swap in the import at the callsite.

**Concrete rules:**
- Read output shows totals; check before every Edit/Write to an existing file.
- Over 300 lines: extract to `src/cen/<package>/<feature>.py` or `frontend/src/components/<feature>/<Name>.tsx`. Parent file gets a small swap (import + use), not an addition.
- Multi-file plans must state current line counts so "extract vs append" is an explicit decision, not an oversight.
- Functions: keep under 40 lines, single responsibility.

**Known monoliths with deferred decomposition** — flag the tension in commits, don't pretend it's not there:

| File | Lines | Status |
|---|---|---|
| `src/cen/core/engine.py` | 213 | ✅ Decomposed 2026-04. Helpers in `engine_helpers.py` (235), per-node-type runtime handlers in `engine_runtime.py` (301). |
| `src/cen/api/routes/sessions.py` | 383 | ⚠️ Partially decomposed. Audit endpoints moved to `_sessions_audit.py`, exports to `_sessions_exports.py`. Still over the bar — next pass should extract approve/provide_input/rewind. |
| `src/cen/sop/extractor.py` | ~330 | Split into `parser_helpers.py` + `classifier.py` (deferred). |
| `frontend/src/components/StepCard.tsx` | 235 | ✅ Decomposed 2026-04. StepHeader, FieldInput, FileFieldInput moved to `step_components.tsx` (333 — borderline; can split by input type if it grows). |
| `frontend/src/components/DAGViewer.tsx` | ~683 | Already split internally (DAGCanvas, NodeRect, EdgePath, DetailPanel) — promote to separate files. |
| `frontend/src/components/SOPStudio.tsx` | ~498 | Extract UploadCard, SOPList, ReviewPane, NodeTable, ValidationSummary into `components/sop/`. |
| `frontend/src/api.ts` | ~340 | Split by resource (`api/cases.ts`, `api/sop.ts`, `api/concierge.ts`) — only do this when `api.ts` exceeds 500. |

When you touch one of these for an unrelated reason, do not "tidy up" — the decomposition is its own PR. When the file is the *target* of your change, do the extraction first.

### 4.10 Orchestration Rules (for agentic sessions)

- **Parallelism first** — independent reads/searches in a single block.
- **Strict write discipline** — `Read` the target block before every modification. Don't re-read after writing unless a tool reports an error.
- **Speculative search** — `Grep` the codebase before asking the user for clarification.
- **Plan → Code → Verify → Fix → Report** — never report done until verification passes (§6).
- **Options before code** — present 2-3 approaches for non-trivial changes; let the user choose.

---

## 5. Frontend Standards

**Goal**: a navigator or patient with no technical background completes a workflow without instructions.

### Layout

- **Three-frame Executor** *(target)*: left = nav + session list + stepper, middle = current step (form, upload, history), right = AI concierge. Today's Executor is two-frame; rebuild on roadmap (§8).
- **DAG Viewer** is a separate tab with pan/zoom, TB/LR layout toggle, fullscreen, hover tooltips.
- Tabs: **Executor**, **DAG Viewer**, **Audit**, (planned) **SOP Upload**.

### UX Principles

- **Plain language always** — see forbidden-terms table below.
- **Action-oriented** — lead with "What needs your attention." Status badges with plain labels.
- **Reversible by default** — destructive actions get confirmation modals; reversible ones get undo toasts. Never confirmation-modal a reversible action.
- **Progress is visible** — stepper for workflow position; long ops get descriptive copy ("Generating your draft appeal letter, this may take 30 seconds…"), never an unannotated spinner.
- **Mobile-aware** — three-frame collapses to single-column with bottom-sheet drawers.
- **Accessibility** — WCAG 2.1 AA target. Keyboard nav across frames, ARIA landmarks, focus moves to new step on advance.

### Forbidden UI Language

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

### Empty States, Errors, Confidence

- Every list/surface has an empty state with plain explanation + clear CTA.
- Every error: plain-language description + suggested next step (no HTTP codes, no tracebacks).
- Below-threshold AI confidence → yellow "Needs verification" badge with source link. High confidence → muted "Verified by AI" indicator.
- Concierge system prompt: not-a-lawyer/doctor/financial-advisor disclaimer, refuse personalized legal/medical advice, scope to current step, cite the step. Visible disclaimer beneath chat input.

---

## 6. Verification Process

**After EVERY code change, run all applicable checks below before reporting done.** If a check is N/A, say so and why. Final report includes a checklist.

### A. Build & Type Safety (always)

| # | Check | Command | Pass |
|---|-------|---------|------|
| A1 | Backend type check | `mypy src/cen` | exit 0 |
| A2 | Tests for new/modified code | `pytest tests/<path> -v` | all pass |
| A3 | Full backend suite (when core/engine/store touched) | `pytest tests/ -v` | all pass |
| A4 | Frontend type check (web touched) | `cd frontend && npx tsc -b` | exit 0 |
| A5 | Frontend build (deploy or build config changed) | `cd frontend && npm run build` | exit 0 |
| A6 | Frontend lint (web touched) | `cd frontend && npm run lint` | exit 0 |

### B. Database & Schema (when models/queries change)

- Migration / schema-init updated for every new column/table; nullable or `DEFAULT`.
- Test schema (`:memory:`) matches dev DB; new table registered in startup `_init_db`.
- Indexes on hot-path filter columns. FK-style refs (`case_id`, `project_id`, `node_id`) consistent across tables.
- Pydantic model in `models.py` matches table field-by-field.
- Backfill plan documented in commit message for any column that breaks existing rows.

### C. Privacy & PII (Non-Negotiable #1)

- New code touching `context` runs scrubber before audit/log/LLM (grep `scrub(` in diff).
- New endpoints validate via Pydantic — no raw `dict` shoved into context.
- New log statements: no patient name/DOB/SSN/address/raw context dicts.
- Concierge prompt path runs scrubber on system + user + history.
- New uploads enforce size cap and content-type whitelist server-side.

### D. Multi-Tenant Hooks (Non-Negotiable #8)

- Every new mutation accepts `owner_id`; every query filters by `owner_id` (or via parent that does).
- New routes use the auth dependency (even when stub).
- New tables holding case/project data carry nullable `owner_id`.
- Cross-tenant negative test exists for every new mutation route — asserts user B can't read/update user A's resource. Tightens when real auth lands.
- Public endpoints (when added) follow §3 Public Endpoint Exception Pattern.

### E. Audit Trail (Non-Negotiable #2)

- Every state change emits `AuditEvent` via audit store; payload is scrubbed.
- Hash chain unbroken; new event types added to canonical list and emitted via `AsyncEventBus.emit(...)`.
- Live verification: `sqlite3 ./data/cen.db "SELECT event_type FROM audit_events WHERE case_id='<uuid>' ORDER BY id"`.
- Audit append failures wrapped in try/except — never block user mutation.

### F. Engine Resumability (Non-Negotiable #3)

- New ACTION node with side effects checks `context["__node_outputs"][node_id]` before executing; caches output after.
- Resume test exists: pause mid-workflow → resume → assert side-effecting call made exactly once.
- New `SessionStatus` values added to state machine + `models.py` enum.
- Module version pinned on case creation; resume loads pinned version, not current.

### G. API ↔ Frontend Alignment

- Live route mounts: `curl -o /dev/null -w "%{http_code}" http://localhost:8000/api/<route>` returns 200/422 (not 404).
- OpenAPI regenerates cleanly (`/docs`).
- `frontend/src/api.ts` has a method per new endpoint; `frontend/src/types.ts` matches Pydantic field-by-field.
- Frontend handler calls the new method; new tabs reachable from `App.tsx` nav.
- No CORS errors against `localhost:8000`.

### H. Live E2E Smoke (every new mutation endpoint)

Run a real curl lifecycle against the running dev server: login → CREATE → LIST → UPDATE → DELETE/archive → cross-tenant attempt (must 403/404, never 200) → DB verify → audit verify.

### I. Frontend UI Completeness (web touched)

- Reachable from main navigation; form fields round-trip on reload.
- Empty state present (explanation + CTA). Errors plain-language with next step. Loading states descriptive.
- Mobile responsive (no horizontal scroll, 44px tap targets).
- Language scan against §5 forbidden-terms table.
- Confirmation modals for destructive actions; toasts for reversible.

### J. Security & Hygiene

- No secrets in diff (grep `API_KEY`, `password`, `token`).
- All input Pydantic-validated at entry. No raw SQL string interpolation.
- No PII/credentials in new logger calls.
- New deps justified per §4.7.

### K. Reporting

Final session summary includes a checklist row per applied check, e.g.:

```
| Check | Status |
|-------|--------|
| A1 mypy                        | ✅ |
| A2 pytest tests/core/          | ✅ 14 passed |
| C1 scrubber wired              | ✅ scrub() before audit + LLM |
| D5 cross-tenant negative test  | ✅ user B → user A = 403 |
| F3 resume idempotency test     | ✅ side-effect called once |
| H1-H8 endpoint lifecycle       | ✅ |
```

If any row is ❌/⚠️, fix before reporting done. If N/A, say why.

### Skip Reference by Change Type

- **Backend-only**: skip I; A4/A5 only if frontend imports backend types.
- **Frontend-only**: skip B/D/E/F/H; do A4/A5/A6 + G.
- **Schema-only**: skip G/H/I; B/D/E mandatory.
- **Test-only**: A2/A3 only.
- **Doc-only**: skip everything except a sanity read.

---

## 7. Operational Rules

### Naming

**`Case`** is the canonical name for one execution of a workflow. **`Session`** is the legacy term that survives in two places by design:

1. **Data model**: `Session` Pydantic model, `SessionStore`, `SessionStatus` enum, `session_id` column on the audit table. Renaming these is a database migration plus a change to every read/write path — high blast radius for low UX value, deferred indefinitely.
2. **URL alias**: `/sessions/...` is mounted alongside `/cases/...` and serves the same handlers. Existing API consumers keep working; new code targets `/cases`.

**New code rule**: route files, frontend components, UI strings, and user-facing docs use `case`. Internal data-layer references (the model class, the store class, status enum, audit column) stay `session` until a future migration PR. Don't introduce *new* `session` terminology in routes, components, or docs.

### Git

- **NEVER combine `cd` with `git` in a single compound command** — triggers "bare repository attack" approval prompt. Run `cd` and `git` as separate Bash calls.
- Never auto-commit. Only commit when user explicitly requests.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`).
- Include `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`.

### Deployments

CEN deploys to Render as a single Docker service (frontend built and served by FastAPI). See `Dockerfile` and `render.yaml`. Only deploy when explicitly requested. Pre-deploy: `cd frontend && npm run build` exit 0; `python -c "from cen.api.app import create_app; create_app()"` no errors; schema-init paths idempotent.

### Destructive Operations

Before any DELETE/DROP/rm:
1. Confirm exact scope with the user.
2. Check dependencies (FK refs, in-flight sessions, audit constraints).
3. Specific WHERE clauses — never delete-all when user specified one.
4. For audit-relevant data, prefer redaction (null PII, preserve hash chain) over deletion.
5. Don't delete `data/uploads/`, `data/cen.db`, or other infra paths the app needs.

### User-Facing Commands (PowerShell, not bash)

User runs commands in PowerShell on Windows:
- `Remove-Item -Recurse -Force` (not `rm -rf`)
- `cd C:\path\to\dir` (backslashes)
- `$env:VAR = "value"` (not `export`)

The Bash tool here uses Unix syntax internally (Git Bash); commands TO THE USER must be PowerShell.

### Autonomous Behavior

Loop: **Plan → Code → Verify → Fix → Report**. Don't report until verification passes. If a build/test fails, fix autonomously. Only ask on architectural ambiguity. Multi-file features use Plan Mode first. Present **options before code** for non-trivial changes.

---

## 8. Roadmap (active design questions)

Open architectural decisions affecting near-term work. Update as decisions land.

### Tier 1 — Blocking

- Project layer above sessions (one Project per patient, multiple sessions per project) — schema impact.
- Patient self-service vs navigator-operated as v1 target — UX impact.
- Real PHI vs synthetic-only for v1 — determines whether file encryption, BAA-backed LLM, and auth must land first.
- Auth strategy: minimal operator login now vs dev-only-no-PHI until dedicated milestone.
- Engine idempotency strategy: skip-list + cached outputs (recommended) vs per-node snapshot vs mark-idempotent flag.
- Session → Case rename: coordinated now vs deferred to Executor rebuild.

### Tier 2 — Design in Progress

- Three-frame Executor rebuild.
- Step-pause mechanism: declarative `input_schema` + auto-pause on missing CONDITION fields.
- File upload + artifact storage with encryption at rest and audit on every up/download.
- AI concierge v1: stateless prompt builder + scrubber on assembly + scope guardrails + history truncation. RAG later.
- Schema migration framework (alembic or equivalent) before next round of schema changes.
- Module version pinning on session creation.
- Optimistic concurrency (`version` column) on Session updates.

### Tier 3 — Backlog

SOP-to-DAG generator · RAG concierge · multi-language · mobile collapse · retention worker · Postgres migration · session forking/templates · printable case dossier export.

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
| Architecture (when added) | `docs/architecture.md` |
| Deployment runbook (when added) | `docs/deployment.md` |
| State machine reference (when added) | `docs/state-machine.md` |

### Skills

| Skill | Purpose |
|-------|---------|
| `/commit` | Stage and commit with conventional message |
| `/summarize` | Summarize session work and decisions |

### Subagents

- **Explore**: codebase search across >3 files.
- **Plan**: features touching 3+ files or complex architecture.
- **general-purpose**: multi-step research, keyword searches.
