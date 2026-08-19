# CEN — Session Log

> **Read this file at the start of every new Claude Code session.**
> Top section reflects current reality. Bottom section is the append-only history.

## Current State

### Project overview

CEN (Community Equity Navigators) is an AI Concierge platform for No Surprises Act compliance and patient financial advocacy. Community navigators use it to walk patients through charity care, medical-debt cancellation, insurance appeals, benefits enrollment, and community-resource referrals. The prototype runs end-to-end: a navigator picks a case, the engine drives them through a declarative AOP/DAG workflow with input prompts, approval gates, and now bounded repeating steps (negotiation/appeal rounds); the AI can produce the actual documents (appeal/dispute letters) behind an approval gate; the right-rail Concierge answers questions grounded in a step-scoped FAQ library and lets navigators enter case data conversationally; SOP Studio ingests SOP documents into reviewable workflow drafts with auto-assigned metadata tags a human curates before promotion; the Dashboard buckets cases by attention-state; and every step lands in an append-only audit chain. Single-operator stub auth; synthetic data only. **Production runs real AI synthesis via Groq.**

**Repo**: https://github.com/keatstx/CEN
**Live**: https://cen-48pm.onrender.com (single Docker service; FastAPI serves the built React frontend). Note: the bare `cen.onrender.com` is NOT this service; the `-48pm` host is.

**Sister project**: FairClaims (https://github.com/keatstx/fairclaims, `fairclaims.onrender.com`) is an independent public marketing site that duplicated CEN's concierge slice. It does **not** share CEN's API key (corrected 2026-08-19 from the Groq console: two distinct keys — `FairClaims API Key for Groq` `gsk_...e8AP`, dormant since 2026-05-01, and `key-ptkeat-gmail-com` `gsk_...sarv`, which is the one in Render). They do share the single Groq **project** ("Default Project"), so the project-level model allowlist governs both — which is exactly what took CEN down on 2026-08-16. Independent codebase and deploy otherwise.

### Tech stack

- **Backend**: Python 3.9, FastAPI, async-first; aiosqlite storage; structlog logging
- **Engine**: NetworkX DAG executor. Thin dispatcher (`engine.py`) + per-node-type handlers (`engine_runtime.py`) + pure helpers (`engine_helpers.py`) + bounded-loop controller (`engine_loops.py`) + GENERATE handler (`engine_generate.py`)
- **LLM**: pluggable via Protocol — `mock` (tests/dev default), `gguf` (local llama.cpp), `api` (OpenAI-compatible). **Production uses `api` → Groq** (`openai/gpt-oss-20b`, stepping down to `openai/gpt-oss-120b`). `CEN_LLM_MODEL` is an **ordered preference list**, not a single id: the first model the provider still offers is resolved lazily, cached, and re-resolved after a failure. Both models are Apache 2.0 open-weights.
- **Privacy**: regex PII scrubber by default (`CEN_PII_BACKEND=regex`); Presidio swap available. Scrubber is injected into the engine and runs before every LLM prompt (GENERATE + the ACTION llm_prompt path + concierge).
- **Frontend**: React 19 + Vite 7 + TypeScript + Tailwind 4. **No state library** — state lifted to `App.tsx` via hooks (`useCaseSession`, `useSOPSession`, `useLayoutCollapse`, `useCurrentUser`). Hand-rolled SVG DAG rendering (no react-flow/dagre).
- **Tests**: pytest 8 + pytest-asyncio (`asyncio_mode = auto`); httpx ASGITransport for API tests. No frontend test framework (bar is `tsc -b` + lint + build + manual/browser smoke).
- **Deploy**: Render Docker service. `render.yaml` sets `CEN_LLM_BACKEND=api`, `CEN_LLM_API_BASE=https://api.groq.com/openai/v1`, `CEN_LLM_MODEL=openai/gpt-oss-20b,openai/gpt-oss-120b`, `CEN_LLM_API_KEY` (dashboard secret), `CEN_DB_PATH=/tmp/cen.db` (ephemeral), `deployment_mode=synthetic` (bypasses the BAA gate — safe only because no real PHI). **Render dashboard env vars override `render.yaml`** — a value set in the Environment tab wins, and blueprint changes will not take effect until the dashboard value is changed too (this cost a deploy cycle on 2026-08-19).

### How to run locally

```bash
# Backend (mock LLM by default; serves built frontend if present)
uvicorn cen.api.app:create_app --factory --reload --port 8000

# Frontend dev
cd frontend && npm run dev    # port 5173

# Tests
pytest tests/ -v              # 500 currently passing
mypy src/cen                  # (needs `pip install mypy` + types-networkx to silence stub noise)

# Frontend checks
cd frontend && npx tsc -b && npm run lint && npm run build

# Docker build (matches Render)
docker build -t cen-test . && docker run --rm -p 10001:10000 cen-test

# Local hosted LLM (OpenAI-compatible). CEN_LLM_MODEL takes a single id
# or an ordered preference list ("a,b") - first one offered wins.
CEN_LLM_BACKEND=api CEN_LLM_API_BASE=http://localhost:11434/v1 CEN_LLM_MODEL=llama3 \
  uvicorn cen.api.app:create_app --factory --reload

# Regenerate the FAQ function-tag overlay (LLM mode needs a real key)
python -m cen.core.faq_classify --mode heuristic   # deterministic, default
# CEN_LLM_BACKEND=api CEN_LLM_API_KEY=... python -m cen.core.faq_classify --mode llm
```

### Architecture at a glance

- **Layered**: routes (HTTP) → services/engine (logic) → stores (aiosqlite). CLAUDE.md §3 is canonical.
- **Engine is pure**: takes session + module + context, returns a result; no side effects outside session/audit stores. Pure DAGs take the unchanged topological walk; loop-bearing modules take a condensation-based walk (`engine_loops.run_with_loops`).
- **Workflows are data**: AOP/DAG JSON in `src/cen/modules/` (six built-in, loaded at startup) and user-promoted from SOP Studio. Document generation and loops are metadata/edge annotations, not new node types.
- **Three-panel FlowUX**: `Layout.tsx` = collapsible LeftNav (Home/Dashboard/Executor/Workflow Map/SOP Studio/Settings/Profile) + center "Studio" + persistent right-rail Concierge. "Concitor · FlowUX Studio" co-brand.
- **Audit-as-feature**: every node execution, input, upload, approval, concierge turn, SOP promotion, and loop escalation emits a hash-chained `AuditEvent`.

### What's shipped

**Workflow engine** (`engine.py` + `engine_runtime.py` + `engine_helpers.py` + `engine_loops.py` + `engine_generate.py`)
- Four node types: ACTION, CONDITION, HANDOFF, APPROVAL. No fifth type.
- **GENERATE** — document production as an ACTION subtype (`metadata.action_kind == "generate"` + `GenerateSpec`). Assembles a prompt from `input_fields`, PII-scrubs it, calls the LLM, writes `{node_id}_document` + provenance `{model, prompt_version, timestamp, output_kind}` into context. Idempotent (fires once per case/iteration). Handler in `engine_generate.py`. Commit `1b8819f`.
- **Bounded loops (LDCG)** — a strongly-connected region closed by a `loop_back` edge + a `LoopSpec` on the entry (`exit_node`, `exit_condition_field`, `exit_when`, `max_iterations`, `on_limit_next`). Controller re-runs the body up to the cap, checks the exit condition each pass, escalates to a human gate (APPROVAL/HANDOFF) on cap. Unannotated cycles still raise `CycleDetectedError`. Output cache is namespaced per-iteration (`ExecutionState.loop_suffix`). Pure DAGs are byte-identical (isolated code path). v1 contract: one entry with `LoopSpec`, no branching CONDITION inside the loop body. Commit `39c8400`.
- Idempotent resume cache (`context["__node_outputs"]`) across all node types; `#<iteration>` suffix inside loops.
- HANDOFF `pause_on_handoff` → `AWAITING_EXTERNAL`; auto-derive CONDITION prompts; approval auto_set; rewind-to-prior-step.
- Scrubber injected into `AsyncWorkflowEngine`; the ACTION `llm_prompt` path now scrubs too (pre-existing gap closed in `1b8819f`).

**Workflow library** (`src/cen/modules/`, six built-in v2 modules)
- `charity_care_navigator`, `debt_cancellation_engine`, `insurance_appeal_assistant`, `benefits_enrollment_navigator`, `community_resource_router`, `master_case_orchestrator`.
- **All ~200 steps carry namespaced tags** (`function:*`, `domain:*`) backfilled in `de690fa`.
- `insurance_appeal_assistant.draft_appeal` is a GENERATE node (appeal letter) with `counselor_qa` (APPROVAL) before `submit_appeal` (`37f76fc`).
- `debt_cancellation_engine.negotiation_round` is a real bounded loop (3 rounds → escalate to `escalation_router`, now a HANDOFF) (`f550726`).

**Metadata tags** (`src/cen/core/tags.py` + `src/cen/seed/tag_vocabulary.json`)
- Namespaced facet tags on `NodeMetadata.tags`; `faq_pin` for explicit step→FAQ pinning. Project-level vocabulary (controlled `function`/`domain`/`sensitivity` facets + open `attribute`).
- Structural auto-assignment at SOP extraction (`PHASE`/node-type → `function:` tags) in `extractor.py`.
- **Tag editor in SOP Studio** (`frontend/src/components/sop/TagEditor.tsx`) — the first node-editing surface; chips + autocomplete from the vocabulary + amber flag on out-of-vocab tags; wired to the `PATCH /sop/{id}/draft/nodes/{id}` endpoint (which now accepts `tags`/`faq_pin`). `GET /sop/tag-vocabulary` feeds it. Commit `bf5282f`.
- Validator warns (never blocks) on out-of-vocabulary tags.
- **FAQ function-tags** (`src/cen/core/faq_classify.py` + `src/cen/seed/faq_function_tags.json`) — regenerable overlay mapping FAQ question → `function:` tag, so step tags overlap FAQ tags. Heuristic mode ran (151/200 tagged); `--mode llm` sharpens it via Groq. Commit `06dc73e`.

**AI Concierge** (right rail, persistent)
- Multi-source RAG: FAQ + workflow-step + case context, normalized-fused.
- **Step-scoped FAQ**: FAQs sharing a `function:` tag with the current step get boosted; citations carry a `from_step` flag rendered as a "From this step" badge (`5b30bfa`). `faq_pin` always surfaces pinned FAQs.
- LLM-grounded synthesis (Groq in prod); rule-based fallback for mock/failure.
- **Chat feeds the center step** (fixed `a78bffd`): answering in the concierge extracts values that auto-fill the Step Card draft. `App.tsx` wires `onSuggestionsUpdate` → shared `suggestions` state (this was severed — the root bug). Structured fields via `RegexExtractor`; dates normalized to ISO `YYYY-MM-DD`; **free-text (patient name, etc.) via the new `LLMExtractor`** (`suggestions_llm.py`, regex-first, LLM fills gaps, safe fallback, scrub-before-LLM). `_extract_suggestions` is async; auto-selects LLM when a real backend is present, regex for mock.
- Persistent chat history per case; status-aware proactive opener; out-of-scope guardrails.

**Document surfacing** (`frontend/src/components/GeneratedDocuments.tsx`)
- Executor renders AI-drafted documents from context with a "Needs verification" badge, "Drafted by the AI assistant" provenance (no raw model id, per §5), and copy-to-clipboard. `InformationSoFar` filters `_document`/`_provenance` so the card owns rendering.

**Loop observability** (`frontend/src/components/LoopStatus.tsx`)
- "Repeating steps" card in the Executor: "Round N of M" + plain-language status (In progress / Done / "Sent to a specialist"). Reads `context["__loop_state"]` (controller records `iteration`, `status`, `max_iterations`, `label`).

**Executor is form-first** (`Executor.tsx` + `StepCard.tsx`)
- The center panel is the input surface for **every** status, including `AWAITING_INPUT`. Chat assists by extracting values into `suggestions`, which StepCard offers as one-tap Apply chips above the form — it never replaces the form.
- `ChatLedStep.tsx` was **deleted** (`195011e`). It rendered no input controls at all: a "Now asking about" box whose subtitle read "Answer in the chat on the right", a read-only captured-values list, and a Submit disabled until the concierge extracted values. Its "Show all fields" escape hatch reset on every step (component remounts on `key={stepKey}`), so opting out of chat never stuck.

**Concierge grounding** (`core/concierge_grounding.py`, `f2f2c40`)
- `retrieve_input_fields()` — the pending step's own input fields are a retrieval source, scored above FAQs when the question overlaps them. A navigator asking what a field means is answered from the description authored for that field.
- `select_lead()` — the highest-scoring *eligible* chunk leads, regardless of kind. Case-state chunks carry `lead_eligible=False`: their 0.95 is an **inclusion priority** ("the model must know where we are"), not a relevance score, and ranking on it answered "what is charity care?" with "Current step: Collect household income."
- `MIN_FAQ_LEAD_SCORE = 0.30` — calibrated on measured cosines (real matches 0.41/0.39/0.37; the garbage that caused the reported bug 0.24/0.23/0.21). A sub-floor FAQ can still be cited but never asserted as the answer. `no_match` now also states what the step needs.
- All deterministic — **no LLM required**, which is why the concierge kept answering correctly through the Aug 16–19 outage.

**LLM resilience** (`llm/model_resolver.py`, `llm/openai_compat.py`, `llm/factory.py`)
- **Preference list** — `CEN_LLM_MODEL` accepts `a,b,c`; first offered wins. Resolution is lazy (constructor is sync, no network I/O), cached (`/models` is not hit per generate), lock-guarded, and re-resolved once after a failed completion so a mid-process retirement costs one failed call.
- **Generation is optimistic, health is strict** — an unreadable `/models` falls back to the top preference and lets the completion be the test; `is_available()` still returns false because it cannot verify. Requiring `/models` before every generate would turn a flaky discovery endpoint into an outage.
- **Deliberately not auto-discovery** — availability is machine-checkable, quality equivalence is not. A human ranks the list; the resolver only picks from it.
- **`generate_checked()`** returns `LLMGeneration{text, degraded, error}`. The concierge treats a degraded result as a miss and falls through to the rule-based stitcher, so canned mock filler is never labelled `llm_synthesis`.
- **`llm_last_error` on `/ready`** — the last degradation cause, cleared on the next success, with the provider's response body first (the actionable half) and a 600-char cap.

**Dashboard, SOP Studio, cases, exports, uploads** — unchanged this session; see prior entries and CLAUDE.md.

### Non-negotiables in force

1. **PII scrubbing on external boundaries** — before audit, telemetry, and LLM prompt assembly (GENERATE, ACTION llm_prompt, concierge, LLMExtractor).
2. **Append-only audit** — hash-chained; loop escalations recorded via the node-event path.
3. **Idempotent engine resume** — `__node_outputs` cache across all node types; `#iteration` key inside loops (exactly-once per pass). Tests in `test_engine_generate.py`, `test_engine_loops.py`.
4. **Module version pinning** — `Session.module_version` set at creation. (Still ⚠️ partial across all read paths — deferred, see open items.)
5. **Declarative workflows** — GENERATE + loops are metadata/edge annotations, not code branches or new node types (CLAUDE.md §3 #5).
6. **Confidence + provenance** — GENERATE outputs carry full provenance; concierge citations carry `kind` + `from_step`.
7. **API-first**; **8. Multi-tenant stub** (`owner_id`, stub `default-operator`).

### Open items

1. **Module version pinning is partial** — every action resolves the *current* engine by module name, ignoring `session.module_version`. Prerequisite for safe live workflow editing. (Flagged 2026-07-22; deferred because GENERATE/loops don't strictly need it.)
2. **Rewind-into-loop** doesn't reset a region (bare-`node_id` cache clear misses the `#iteration` keys). No live risk yet (rewind + loops not combined in shipped flows). Deferred with the loop engine.
3. **DAGViewer doesn't render loops** — Kahn's topological layout doesn't handle cycles; a loop-bearing workflow shows its skeleton and the loop_back edge renders oddly. Cycle-capable layout (react-flow decision) deferred.
4. **Agentic task engine (3c)** — `AgenticTaskSpec` schema exists but no executor. Decide after GENERATE proves the pattern. Deferred.
5. **API/MCP bindings + node system-prompt overrides (3d)** — deferred until real auth + encryption-at-rest exist (PHI-egress + guardrail-override risk).
6. **Presentation layer (3a)** — descoped to a single `metadata.presentation_ref` pointer (schema only, no UI).
7. **FAQ function-tags are heuristic** — `faq_function_tags.json` was generated with the keyword pass (over-weights `document_collection`). Run `python -m cen.core.faq_classify --mode llm` (Groq) and commit the overlay to sharpen.
8. **Persistent prod DB** — `CEN_DB_PATH=/tmp/cen.db` resets every redeploy (cases + uploads + generated docs vanish). **This is the one remaining decision before real cases can persist**: a Render persistent disk (~$7.25/mo, forces the free plan to Starter) or Render Postgres. Email drafted for the colleague who foots the bill.
9. **Untracked reference docs** — `BASELINE.md`, `BUSINESS_VIEW.md` (dated 2026-04-30, now stale re FlowUX/GENERATE/loops), and `docs/SPEC_AOP_FLOWUX.md` (the expansion spec) are at repo root/`docs/`, uncommitted. `docs/session_log.md` (this file) is committed going forward.
10. **Session → Case rename** — data-layer stays `session` by design (CLAUDE.md §7).
11. **No frontend tests** — `tsc -b` + lint + build + browser smoke is the bar.
12. **PDF SOP parser + LLM SOP extractor** — `.docx` solid, PDF partial, SOP extraction still regex-only.
13. **`is_available()` is not proof of usability** — it verifies the configured model appears in the provider's `/models`, which proves the provider *offers* it, not that our project may *call* it. On 2026-08-19 `/ready` reported `llm_available: true` while every completion 403'd on a project-level model block. The only conclusive probe is a real minimal completion (cached, or startup-only). Not built: it adds an API call to a public unauthenticated endpoint, so the cost/benefit is the owner's call. `llm_last_error` covers the gap.
14. **Stale `llama-3.3-70b-versatile` in the Groq allowlist** — cannot be removed: the console's model picker only lists *current* models, so a retired entry already saved has no checkbox to untick. Harmless (nothing requests it) and left deliberately. Clearing the whole list and re-adding would work, but Groq's behaviour on an empty allowlist (all-allowed vs none-allowed) is unverified and CEN is live.
15. **FAQ library has a content problem** — it contains meta-FAQs *about the product* ("What does the AI Concierge do when I'm at Ongoing Monitoring"), which are lexical magnets for any "what does X mean" question. The 0.30 floor stops them being asserted, but they still occupy citation slots. Some answers also surface jargon that violates CLAUDE.md §5 ("CONDITION node", "APPROVAL node"). Curation, not code.
16. **`FallbackLanguageModel.backend_name` reports the primary** even when the mock answered. `mode` and `llm_last_error` now make degradation visible, so this is cosmetic — but `/ready`'s `llm_backend` still can't be read as "what actually answered".

### Recent test counts and verification status

- Backend tests: **500 / 500 passing** (`pytest tests/ -v`)
- mypy: clean on every module touched this session; the pre-existing backlog remains (missing `networkx`/`presidio`/`llama_cpp` stubs — 4 of them in `llm/gguf.py` alone — plus a few genuine issues in untouched files)
- Frontend `tsc -b` / `npm run lint` / `npm run build`: clean (~302 KB JS, ~89 KB gzip)
- Production verified live 2026-08-19 after the Groq allowlist fix: `/ready` → `llm_available: true`, `llm_model: openai/gpt-oss-20b`, `llm_last_error: null`; `/tlm/generate` → `"banana"` (a real model, not the mock); `/concierge/ask` → `mode: llm_synthesis` with a grounded plain-language answer in 0.67s.
- Also verified live: the form-first Executor (typed a patient name into the centre panel, submitted, workflow advanced two nodes to the approval gate, context persisted, audit chain valid across 4 records) and the grounding fix (field question answered from the field, FAQ question still answered from the FAQ, unanswerable → `no_match` + step recap).
- Last commit: `29aa125` — *fix(llm): don't truncate away the actionable half of a provider error*

## Session History

[Append-only — never edit prior session entries. Newest at top.]

### 2026-08-19 — Form-first Executor + concierge grounding + a three-day silent LLM outage

**Commits (9, all on `origin/main`, deployed + prod-verified):**
- `195011e` feat(executor): form-first center panel — retire chat-led step
- `bdb4e5a` fix(llm): swap retired Groq model and stop the silent mock fallback
- `a588d6d` feat(concierge): collapse citation sources behind a disclosure
- `f2f2c40` fix(concierge): ground answers in the step's own fields, floor the noise
- `18177f0` feat(llm): model preference list so retirements stop being outages
- `af96c6a` feat(llm): surface the last degradation cause on /ready
- `f8e682b` fix(llm): include the provider's error body in HTTP failures
- `29aa125` fix(llm): don't truncate away the actionable half of a provider error
- `c6a9753` docs: session log for 2026-08-19 (first commit of this file; it had stayed untracked despite open item 9 saying otherwise)

**What was done:**

1. **Form-first Executor (the session's actual ask).** The owner reported that users could only interact through the AI chat. Root cause was a hard branch in `Executor.tsx`: on `AWAITING_INPUT` — the one status where input matters — `StepCard` was swapped out for `ChatLedStep`, which rendered **no input controls at all**, only a "Now asking about" box telling the user to answer in the chat, a read-only captured-values list, and a Submit button disabled until the concierge extracted values. The full working form already existed and was unreachable except via a grey "Show all fields" link that reset on every step (the component remounts on `key={stepKey}`). Presented three options; owner chose A (flip the default). `ChatLedStep` deleted, `StepCard` renders for every status, chat demoted to Apply-chip assistance. Frontend-only — `provide_input` remains the single write path, so audit and idempotency are untouched.

2. **Chat rail decluttered.** Every reply rendered its full citation list inline — three to five lines of step labels and verbatim FAQ questions pushing the answer off-screen. Collapsed behind a one-line "3 sources · 1 from this step" disclosure. **Deliberately collapsed, not removed**: non-negotiables #6/#9 require provenance in the UI so navigators can verify before acting. Extracted to `components/chat/CitationList.tsx` (Concierge.tsx was 420 lines, over the §4.9 bar).

3. **Discovered production had been answering from the mock since 2026-08-16.** Asking prod "what is charity care?" returned a verbatim hardcoded string from `llm/mock.py:19` in 0.19s, under `mode: "llm_synthesis"`. Three mechanisms hid it: `FallbackLanguageModel.generate` caught every exception and returned the mock; `is_available()` only checked that `/models` returned 200 (true even after a model is retired); and `backend_name` reports the *primary*, so the "skip the LLM path when the backend is mock" guard never fired. Groq had retired `llama-3.3-70b-versatile` (announced 06-17, shut down 08-16) — the 07-22 session verified real synthesis, which fits exactly.

4. **Concierge grounding.** Owner pasted a transcript: asked what "How many people live in the household?" meant, got a paragraph about requesting environmental exposure records. Reproduced verbatim against prod, then root-caused three stacked defects (missing field retrieval, lead-by-kind instead of by-score, no relevance floor) and fixed all three deterministically. See "What's shipped" above.

5. **Model resilience harness.** Owner asked how to stop managing model migrations. Built the preference-list resolver after presenting options and being explicit that availability is automatable but *quality equivalence is not*. Owner ruled out self-hosting (hosted only, Groq or OpenRouter) and asked for free open-source models — clarified that `openai/gpt-oss-*` **is** open-weights Apache 2.0 (the `openai/` prefix is a publisher namespace, not the OpenAI API) and that the earlier per-token figures were the paid tier, not the free tier they run on.

6. **Chased the last 403 to a Groq console checkbox.** After the swap, `/ready` reported healthy with a resolved model while every completion still degraded. Added `llm_last_error` to `/ready` (no host log access), which showed `403 Forbidden`; added the provider response body, which showed *"blocked at the project level"*; then found the actionable URL had been eaten by my own 300-char truncation and fixed that too. Root cause: the Groq project allowlist held **only** `llama-3.3-70b-versatile`, so the retirement left the project permitted to call exactly one model that no longer existed. Owner enabled both gpt-oss models; verified live immediately.

**Key decisions:**

1. **Form-first over a merged progressive form** — owner chose the smaller change; option B (real inputs with chat live-filling them, keeping the one-question-at-a-time focus) remains available and nothing done for A is wasted.
2. **Citations collapsed, never removed** — a compliance requirement, not a display preference.
3. **`lead_eligible` flag rather than ranking purely on score** — an existing test caught that pure score ranking answered "what is charity care?" with the current step. Inclusion priority ≠ relevance; the distinction is easy to re-break, hence the explicit flag.
4. **Generation optimistic, health strict** — the first resolver draft required a successful `/models` read before every generate, which would have turned a flaky discovery endpoint into a total outage. Existing tests caught it; both behaviours are now pinned by their own tests.
5. **No auto-discovery of "best available" model** — a heuristic silently choosing which model drafts a patient's appeal letter is bad governance under non-negotiable #6 (provenance records `{model, prompt_version}`). A human ranks the list.
6. **`openai/gpt-oss-20b` first, `120b` second** — measured a real concierge prompt at ~1,635 input tokens (320 max out), putting a realistic month at ~$0.09 on 20b and ~$0.19 on 120b, i.e. $0 on the free tier. Cost is not a factor at this volume, so ranked by latency and free-tier headroom instead: 20b is ~2x throughput and the concierge is an interactive rail. Answers are grounded, so model size buys little.
7. **Left the stale llama entry in the Groq allowlist** — see open item 14.
8. **Committed directly to `main`** — flagged at the time; this repo deploys from `main` and the owner asked to commit, push and deploy in one breath.

**Files changed:**

*Frontend* — `components/Executor.tsx` (branch removed), `components/StepCard.tsx` (orphaned `initialValues` dropped), `components/chat/ChatLedStep.tsx` (**deleted**), `components/chat/CitationList.tsx` (NEW), `components/Concierge.tsx` (citation block swapped, `CitationLine` moved out), `App.tsx` (comment), `api.ts` (`input_field` added to the citation-kind union — caught by `tsc`, the §6-G drift check working)

*Backend* — `llm/model_resolver.py` (NEW — `parse_preferences`, `choose_model`), `llm/openai_compat.py` (preference resolution, cached + lock-guarded + retry-on-failure, model-membership availability, provider error body), `llm/factory.py` (`LLMGeneration`, `generate_checked`, `last_error`, `model`), `core/concierge_grounding.py` (NEW — `RetrievedChunk` moved here, field retrieval, `select_lead`, floor, `describe_pending_step`), `core/concierge.py` (field chunks fused, floor applied, lead selection fixed, step-aware no-match, `lead_eligible=False` on case-state chunks), `core/models.py` (`ReadyResponse.llm_model`, `.llm_last_error`), `api/routes/health.py` (resolved model + last error)

*Tests* — `tests/llm/test_model_resolver.py` (NEW), `tests/concierge/test_concierge_grounding.py` (NEW), additions to `tests/llm/test_factory.py` and `tests/llm/test_openai_compat.py`. 440 → 500.

*Config/docs* — `render.yaml` (preference list + a note that dashboard env vars override the blueprint), `README.md`

**Open items raised:**
- **13. `is_available()` is not proof of usability.** It verifies the configured model appears in the provider's `/models`, which proves the provider *offers* it, not that our project may *call* it — `/ready` read `llm_available: true` for hours while every completion 403'd. The conclusive probe is a real minimal completion (cached or startup-only); not built because it adds an API call to a public unauthenticated endpoint, so the cost/benefit is the owner's call.
- **14. Stale `llama-3.3-70b-versatile` in the Groq allowlist**, un-removable via the console (the picker lists only current models). Left deliberately; harmless.
- **15. FAQ library content problem** — meta-FAQs about the product are lexical magnets for "what does X mean" questions, and some answers surface `CONDITION node` / `APPROVAL node` jargon that violates CLAUDE.md §5. Curation, not code.
- **16. `FallbackLanguageModel.backend_name` still reports the primary** after a fallback, so `/ready`'s `llm_backend` can't be read as "what actually answered". Cosmetic now that `mode` and `llm_last_error` expose degradation.
- **Corrections to prior Current State** (not to prior entries, which stay verbatim): the sister-project note claimed FairClaims shares CEN's Groq API key — the console shows two distinct keys, FairClaims' dormant since 2026-05-01. What they share is the Groq *project*, whose model allowlist governs both. Open item 1's "flagged this session" was dated to 2026-07-22 since a newer entry now sits above it.

**The through-line worth remembering:** three independent layers were hiding failures — a fallback that swallowed every exception, a health check that verified the wrong thing, and (mine) a truncation that discarded the actionable half of an error. Each looked healthy while doing the wrong thing. A green `/ready` meant "the host is reachable", not "this works". The diagnostics added to chase it are what turned a three-day silent outage into a URL and a checkbox — and the deterministic grounding work meant the concierge kept giving correct answers the whole time the model was down.

### 2026-07-22 — AOP expansion: GENERATE + bounded loops + metadata tags + chat-to-form fix

**Note on drift:** the prior Current State (dated 2026-05-01) predated several shipped-but-unlogged changes — the 3-panel FlowUX shell + Concitor co-brand + RBAC stub (`1c21da5`, `ab49638`, ~May 20-21) and the flip to Groq in production (`ad3a0ad`). Those were live at the start of this session; the Current State above now reflects them. This entry covers only this session's commits (`1b8819f` onward).

**Commits (13, all on `origin/main`, deployed + prod-verified):**
- `1b8819f` feat(engine): GENERATE node type + additive AOP expansion schema
- `c124422` feat(concierge): namespaced step/FAQ tags drive step-scoped FAQ retrieval
- `bf5282f` feat(sop): tag editor in the review pane — human curation before promote
- `5b30bfa` feat(concierge): "From this step" badge on step-scoped FAQ citations
- `37f76fc` feat(executor): surface AI-drafted documents end-to-end
- `de690fa` feat(modules): backfill function + domain tags across all 6 workflows
- `06dc73e` feat(concierge): function-tag seed FAQs so step-scoped retrieval fires
- `39c8400` feat(engine): bounded loop regions (LDCG)
- `f550726` feat(modules): wire a real bounded loop into debt negotiation
- `6f8771e` feat(executor): loop observability — "Repeating steps" status card
- `e650366` docs: refresh README + CLAUDE.md and loop-related messages to match reality
- `99b189c` chore: gitignore local .gstack/ tooling state
- `a78bffd` fix(concierge): chat answers now populate the center step (all field types)

**What was done:**

The session opened by evaluating a large "FlowUX × AOP expansion" spec against the actual codebase (the AOP engine and FlowUX shell already existed as one system, not two). Rather than write the full 10-section spec, we scoped it down with the owner and built the marquee pieces incrementally, each: build → wire into a real workflow → surface in the UI → verify → deploy.

1. **GENERATE (document production).** Added document generation as an ACTION subtype (not a fifth node type, per Non-Negotiable #5), plus the full additive AOP expansion schema (`GenerateSpec`, `LoopSpec`, `AgenticTaskSpec`; `NodeMetadata` gains `action_kind/generate/loop/tags/faq_pin/presentation_ref/tasks`; `AOPEdge.kind`). All Optional/null-default, so old module JSON loads unchanged. Injected a PII scrubber into the engine (and closed a pre-existing gap where the ACTION `llm_prompt` path sent context to the LLM unscrubbed). Wired into `insurance_appeal_assistant.draft_appeal` and surfaced in the Executor with a "Needs verification" affordance behind the existing `counselor_qa` approval gate. Live-smoke-verified on prod: a real Groq-authored appeal letter grounded in the case.

2. **Bounded loops (LDCG).** The engine now runs controlled repeating regions. Detection via strongly-connected components; validation relaxes acyclicity only for annotated bounded regions; execution uses a condensation-based walk so pure DAGs are byte-identical. The controller re-runs the body up to `max_iterations`, checks the exit condition, and escalates to a human gate on cap. Output cache namespaced per-iteration. Wired into `debt_cancellation_engine` (the old fake negotiation loop, which never looped back, became a real 3-round loop → HANDOFF escalation). Added the "Repeating steps" observability card. Live-smoke-verified on prod: 3 rounds then escalation.

3. **Metadata tags (whole subsystem).** Namespaced facet tags on steps and FAQs. Built: the vocabulary + `core/tags.py`; structural auto-assignment at SOP extraction; the SOP Studio tag editor (first node-editing UI, backed by the previously-unused `patchSOPNode` endpoint) + `GET /sop/tag-vocabulary`; validator warnings; backfill across all 6 modules (~200 steps); FAQ function-tagging via a regenerable overlay (`faq_classify.py`, heuristic pass 151/200); and the "From this step" provenance badge. Replaced the earlier `faq_scope` idea with `tags` (primary) + `faq_pin` (override) per the owner's decision.

4. **Chat-to-form bug fix.** User reported chat answers weren't populating the center step. Root-caused to three layers: (a) `App.tsx` never passed `onSuggestionsUpdate`, so the Concierge's extracted values were dropped before reaching the shared state the Step Card reads (the core break); (b) the date matcher missed ISO and returned un-normalized US dates a date input can't consume; (c) free-text fields (patient name) were never extracted by design ("leave for the LLM extractor," which was never built). Fixed all three: wired the callback (merge-by-key), normalized dates to ISO, and built the `LLMExtractor` (`suggestions_llm.py`) — regex-first, LLM fills only the gaps, degrades to regex on any failure, scrubs chat before the LLM. Live-verified on prod: "her name is Maria Lopez, DOB 1980-05-01" → both fields extracted via Groq.

5. **Ops + docs.** Diagnosed why prod showed `llm_available: false` — a Groq `organization_restricted` flag (Groq read CEN + the FairClaims sister project as two free-tier accounts). Owner had the restriction lifted and consolidated both projects to one Groq key; confirmed `llm_available: true` and real synthesis on prod. Rewrote the stale README, corrected CLAUDE.md's now-false claims (idempotency cache shipped; loops are supported as bounded regions; generation/loops are metadata not a fifth type), and updated the SOP validator/promoter cycle messages. Verified the live deploy via browser (gstack `/browse` needed a `restart` to start its server on Windows — logged as a learning).

**Key decisions:**

1. **GENERATE and loops are metadata/edge annotations, not new node types** — preserves the "four node types are sufficient" non-negotiable; GENERATE reuses the entire ACTION runtime (pause, cache, auto_set).
2. **Condensation-based loop walk, gated on loop presence** — pure DAGs keep the exact old topological walk, isolating all risk to loop-bearing modules (AC-L5).
3. **v1 loop bodies contain no branching CONDITION** — the controller makes the loop decision via `exit_condition_field`, avoiding `nx.descendants` over a cyclic graph.
4. **Tags: namespaced list, vocabulary at project level, assignment per step** — a shared dictionary makes steps/FAQs comparable; specificity lives in the per-step combination. `tags` replaced `faq_scope`; `faq_pin` kept as an exact-match override.
5. **FAQ tags are function-only, not domain** — domain is already handled by the existing module-name FAQ scoping; a domain tag on every FAQ would make "From this step" fire indiscriminately. Function tags create genuine step-level overlap.
6. **LLMExtractor is regex-first, LLM-fills-gaps** — never does worse than the deterministic v1; auto-selected only when a real backend is present so tests stay deterministic.
7. **Scrub before the LLM in the extractor** — consistent with GENERATE/concierge. With the regex scrubber, ordinary names pass through so extraction works; a future Presidio deployment would degrade name extraction (same tension as GENERATE), resolved at the deployment/BAA policy level.
8. **Did NOT commit `BASELINE.md`/`BUSINESS_VIEW.md`/`SPEC_AOP_FLOWUX.md`** — the first two are stale dated snapshots, the spec was explicitly not wanted as a deliverable. Left untracked.

**Files changed:**

*Backend (engine + core)*
- `src/cen/core/models.py` (GenerateSpec, LoopSpec, AgenticTaskSpec; NodeMetadata + AOPEdge fields; ConciergeCitation.from_step; FAQ.tags; NodeMetadata.tags/faq_pin)
- `src/cen/core/engine.py` (scrubber inject; loop-aware load_aop + execute dispatch)
- `src/cen/core/engine_runtime.py` (iteration-aware cache key; GENERATE branch; scrub the llm_prompt path)
- `src/cen/core/engine_generate.py` (NEW — GENERATE handler)
- `src/cen/core/engine_loops.py` (NEW — region detection/validation, controller, skeleton walk)
- `src/cen/core/tags.py` (NEW — vocabulary + helpers), `src/cen/core/faq_classify.py` (NEW — heuristic/LLM FAQ tagger + CLI)
- `src/cen/core/faq_store.py` (tags column + migration + tag-boost search), `faq_import.py` (async tags + overlay), `concierge.py` (from_step, async `_extract_suggestions`, scrubber), `suggestions.py` (ISO date normalization), `suggestions_llm.py` (NEW — LLMExtractor)
- `src/cen/sop/extractor.py` (structural tag assignment), `validators.py` (unknown-tag warning + updated cycle message), `promoter.py` (scrubber param + updated message)
- `src/cen/api/dependencies.py` (scrubber DI + get_scrubber), `app.py`, `routes/workflows.py`, `routes/sop.py` (scrubber wiring, NodePatchRequest tags/faq_pin, `/sop/tag-vocabulary`), `routes/concierge.py` (FAQ tags + scrubber)

*Modules + seed*
- `src/cen/modules/insurance_appeal_assistant.json` (draft_appeal → GENERATE)
- `src/cen/modules/debt_cancellation_engine.json` (negotiation_round → bounded loop; escalation_router → HANDOFF)
- All 6 `src/cen/modules/*.json` (tag backfill)
- `src/cen/seed/tag_vocabulary.json` (NEW), `src/cen/seed/faq_function_tags.json` (NEW overlay)

*Frontend*
- `frontend/src/App.tsx` (onSuggestionsUpdate wiring)
- `frontend/src/components/GeneratedDocuments.tsx` (NEW), `LoopStatus.tsx` (NEW), `Executor.tsx` (both wired in), `InformationSoFar.tsx` (filter document/provenance)
- `frontend/src/components/sop/TagEditor.tsx` (NEW), `SOPStudio.tsx` (Tags column), `Concierge.tsx` (from_step badge)
- `frontend/src/types.ts`, `frontend/src/api.ts` (tags, faq_pin, TagVocabulary, getTagVocabulary, from_step)

*Docs + chore*
- `README.md` (rewrite), `CLAUDE.md` (corrected loop/idempotency/type claims), `.gitignore` (`.gstack/`)

*Tests (backend 430 → 440 across the session; several increments)*
- `tests/core/test_engine_generate.py`, `test_engine_loops.py`, `test_models_ext.py`, `test_tags.py` (NEW)
- `tests/concierge/test_tag_retrieval.py`, `test_faq_classify.py`, `test_suggestions_llm.py` (NEW); `test_suggestions.py` (date ISO/normalization)
- `tests/modules/test_generate_wiring.py` (NEW — GENERATE + loop wiring guards)
- `tests/sop/test_editor_api.py` (patch tags + vocabulary endpoint), `tests/sop/test_validator.py` (unknown-tag warning)

**Open items raised:**
1. **Persistent prod DB** remains the one blocking decision before real cases survive a redeploy (~$7.25/mo Render disk). Email drafted.
2. **Module version pinning** should be completed before live workflow editing (Requirement 4) is built.
3. **FAQ function-tags** should be regenerated with the Groq LLM pass and committed to improve step-scoped FAQ precision.
4. **Rewind-into-loop reset** and **cycle-capable DAGViewer** are the two flagged loop follow-ups.
5. **Untracked docs** (`BASELINE.md`, `BUSINESS_VIEW.md`, `docs/SPEC_AOP_FLOWUX.md`) need a keep/refresh/discard decision.

---

### 2026-05-01 — Documentation pass + lift concierge into FairClaims

**Commits in CEN:** none (no source code changed)

**Commits in sister repo `keatstx/fairclaims`** (separate project, separate deploy):
- `b13d142` Add FairClaims AI concierge: FastAPI backend + floating chat widget
- `08f2f73` Switch Render plan to free tier (no persistent disk)
- `17dec77` Fix FAQ seed-path lookup under non-editable wheel install

**What was done:**

This session was bookended by two pieces of work — both substantial, neither modifying CEN source:

*Project-level documentation (CEN repo, untracked)*

- `BASELINE.md` (root) — comprehensive engineering baseline: top-level capabilities, layered backend architecture with key modules + LOC, full inventory of 51 API endpoints, frontend component catalog with LOC, data + persistence map, test coverage by area, six built-in workflows summary, dependency tree, compliance-posture matrix mapping each Non-Negotiable to current status, known monoliths with extraction plans, gaps split into Tier 1/2/3, 19 sequenced follow-on actions grouped Hardening → Functionality → Maintainability → Vision, instructions for using the doc as a measurement reference. Written for engineers.
- `BUSINESS_VIEW.md` (root) — business-user-facing twin: who uses it (navigator / supervisor / patient / compliance), the five surfaces in plain English, six workflow phase tables (Master Orchestrator, Charity Care, Insurance Appeal, Benefits Enrollment, Debt Cancellation, Community Resource Router), the four step types described conversationally, six information-source map, run-time loop with idempotent resume + version pinning, SOP authoring flow as Word-doc → live workflow, audit trail explained, three-tier privacy posture (Synthetic / Local-only / Production-with-BAA), what's working today, gap groups by what they unblock (real PHI / smarter workflows / patient self-service / smarter assistant / scale), five expansion themes, five load-bearing differentiators. No code, no jargon. Written for product / business / leadership readers.

Both files are at repo root and currently untracked. Decide where they live (repo root vs `docs/`) before committing.

*Lift CEN's concierge slice into a separate FairClaims marketing site*

A static HTML/CSS/JS marketing site at `https://github.com/keatstx/fairclaims` (existing, separate repo) needed an AI concierge for resident-facing FAQ chat. The constraint: completely independent — no shared code, no shared backend, no shared deploys with CEN. The CEN concierge code was duplicated (not extracted into a shared package) and adapted for a stateless, public, no-PHI context.

Six phases over the session:

1. **Backend skeleton** — created `backend/` directory in fairclaims repo: pyproject.toml, FastAPI app factory, `/health` route, `.env.example`.
2. **Core concierge lift** — copied verbatim or lifted-with-adaptations: `llm/{base, mock, openai_compat}.py` (verbatim), `llm/factory.py` (dropped gguf branch; later simplified to drop FallbackLanguageModel wrapper too — see decision #3), `privacy/pii_scrubber.py` (regex only, dropped Presidio), `core/{faq_store, faq_import, concierge, concierge_prompt, models}.py` (Session/AOP/SOP/chat-history surfaces stripped). `prompts/concierge.md` forked with resident tone (not navigator tone). FAQ seed sourced from `C:\Users\Patrick\Downloads\FAQ\FairClaims_Resident_FAQ_Master.md` — the resident-tone Q&A library, ~108 entries — copied to `backend/seed/`.
3. **FAQ ingestion + retrieval round-trip** — wired `dependencies.py`, single public `POST /concierge/ask` endpoint, app.py seeds FAQ store on startup, mock LLM round-trip working.
4. **Groq + question logging + admin endpoints** — `visitor_hash.py` with weekly-rotated salted SHA256, `core/questions_log_store.py` (append-only `questions_log` table, never raises on append failures, supports `unmatched(since)` and `digest(days)` queries), `api/routes/admin.py` with two bearer-token-gated endpoints (`/admin/questions/unmatched`, `/admin/questions/digest`). LLM swapped to Groq via `openai_compat` (free tier, OpenAI-compatible API at `https://api.groq.com/openai/v1`, model `llama-3.3-70b-versatile`).
5. **Widget + static serving** — `js/concierge-widget.js` (~270 LOC vanilla IIFE, Lucide MessageCircle SVG inlined, fixed bottom-right bubble, expands to 380×560 panel, mobile takeover under 600px, fetch logic with graceful 503/network-error fallback), `css/concierge-widget.css` (reuses FairClaims design tokens — `--gold #D4A843`, `--navy #0B1D3A`, `--font-heading`, `--border-radius`, `--transition` — z-index 1001 above navbar's 1000). Tags injected into all 10 HTML pages (index.html + 9 pages/*.html). FastAPI mounts `StaticFiles` last so API routes win precedence; same-origin deploy means no CORS configuration needed.
6. **Render deploy** — Dockerfile (Python 3.11-slim, copies backend + static assets), render.yaml (later switched from `plan: starter` to `plan: free` after user signaled cost concern; disk block dropped because free tier has no persistent disk; `FAIRCLAIMS_DB_PATH=/tmp/fairclaims.db` ephemeral), `.gitignore`. Custom domain `fairclaims.us` reserved at registrar but not yet mapped (Settings → Custom Domains step pending).

Verification along the way: 25 backend tests written (test_pii_scrubber, test_faq_import using the real seed file, test_concierge for guardrail/no_match/synthesis paths, test_questions_log_store, test_visitor_hash with week-rotation property tests). All 25 pass.

Two real bugs caught during deploy:

- **Bug 1: silent mock fallback in production.** When the Groq key was wrong, `FallbackLanguageModel` (CEN's wrapper) silently fell through to `MockLanguageModel`, which returned canned text labeled as `mode=llm_synthesis` — misleading. Fixed by removing the wrapper entirely in fairclaims's factory: primary LLM raises on failure, `_synthesize_with_llm` catches and returns None, rule-based fallback returns FAQ-verbatim with `mode=synthesis`. CEN's behavior unchanged.
- **Bug 2: FAQ seed-path resolution under wheel install.** `faq_import.py` computed the seed path relative to `__file__`, which works under `pip install -e` (dev) but resolves to a non-existent path inside the Docker container (where `pip install /app/backend` puts the package in site-packages). Result: production FAQ table stayed empty, every question got `_NO_MATCH_REPLY`. Fixed by accepting `seed_path` from settings + a `FAIRCLAIMS_SEED_PATH` env var override; Dockerfile sets the env var to `/app/backend/seed/fairclaims_resident_faqs.md`. Boot log now reports `seed_path_setting` so the resolved path is visible.

Naming convention: env vars renamed from `CEN_*` (initial lift) to `FAIRCLAIMS_*` (final) at user request — separation of concerns since the projects are independent.

End-state: `https://fairclaims.onrender.com` is live with a working concierge bubble that answers FAQ-grounded questions via Groq, logs every question (PII-scrubbed) for FAQ-gap research, and exposes admin endpoints behind a bearer token. Custom domain mapping is the only remaining step for the FairClaims project.

**Key decisions:**

1. **Duplicate, don't share.** A `concierge-core` shared library was rejected — would have coupled CEN and FairClaims through versioned imports. Future improvements port by hand. Cost is real but bounded; the projects evolve at different cadences.
2. **Resident library, not navigator library.** CEN's `faq_library.md` (200 FAQs) is written for navigators ("how do I explain the 200% FPL income threshold to a family during outreach"). FairClaims uses `FairClaims_Resident_FAQ_Master.md` (~108 FAQs) written directly for residents ("I got a huge hospital bill — is there really free help?"). Different audience, different tone.
3. **Drop FallbackLanguageModel wrapper in fairclaims.** CEN's wrapper falls through to mock on LLM error, which is acceptable for a navigator workflow; in fairclaims it would emit canned text labeled as `llm_synthesis` and confuse residents. Fairclaims's factory returns the primary directly; the synthesizer's try/except handles the failure and the rule-based path emits `mode=synthesis` honestly.
4. **No chat persistence; question log instead.** The widget renders fresh on every page load — a visitor sees no chat history. But every question writes one row to `questions_log` with PII-scrubbed text + weekly-rotated visitor hash + matched/unmatched flag + page URL. Tells you which FAQs are loadbearing and what's missing, without retaining identifiable trails.
5. **Free tier on Render, accept the trade-offs.** Cost-driven. Means: instance sleeps after 15 min of inactivity (~30s cold start), and `questions_log` resets on every restart (no persistent disk). FAQ store re-seeds automatically from the bundled markdown so chat works after wake. Upgrade to paid + add a disk later when persistence matters.
6. **Single Render service, same origin.** Static site + API served from one FastAPI process — `StaticFiles(directory=..., html=True)` mounted last after API routes. No CORS to configure. Slightly more compute spent on serving HTML/CSS, but operationally simpler than two services and saves the Render bill.
7. **`FAIRCLAIMS_SEED_PATH` env var as a permanent fix, not a workaround.** An alternative was to copy the seed file into the package directory at build time. The env-var override is more flexible (supports custom seed files, supports persistent-disk seed paths in future paid deployments) and the boot log surfaces which path was used.

**Files changed:**

*CEN repo (this repo):*
- `BASELINE.md` (NEW, untracked, root)
- `BUSINESS_VIEW.md` (NEW, untracked, root)
- `docs/session_log.md` (this file — updated)

*FairClaims repo (separate `keatstx/fairclaims`, NOT changes to this repo — listed for cross-reference):*
- `Dockerfile` (NEW)
- `render.yaml` (NEW)
- `.gitignore` (NEW)
- `index.html` + 9 `pages/*.html` (each: added two `<head>` lines for `concierge-widget.css` + `concierge-widget.js`)
- `css/concierge-widget.css` (NEW, ~280 LOC)
- `js/concierge-widget.js` (NEW, ~270 LOC)
- `backend/pyproject.toml` (NEW)
- `backend/.env.example` (NEW)
- `backend/README.md` (NEW)
- `backend/seed/fairclaims_resident_faqs.md` (NEW, copy of Downloads/FAQ resident library)
- `backend/prompts/concierge.md` (NEW, resident-tone fork of CEN's prompt)
- `backend/src/fairclaims_concierge/` package (NEW): `__init__.py`, `config.py`, `visitor_hash.py`, `core/{__init__, concierge, concierge_prompt, faq_store, faq_import, models, questions_log_store}.py`, `llm/{__init__, base, factory, mock, openai_compat}.py`, `privacy/{__init__, pii_scrubber}.py`, `api/{__init__, app, dependencies}.py`, `api/routes/{__init__, admin, concierge, health}.py`
- `backend/tests/` (NEW): `conftest.py`, `test_concierge.py`, `test_faq_import.py`, `test_pii_scrubber.py`, `test_questions_log_store.py`, `test_visitor_hash.py`

**Open items raised:**

1. **Decide whether `BASELINE.md` and `BUSINESS_VIEW.md` belong in repo root or `docs/`.** Currently at root, untracked. Both are reference docs intended to be re-read at the start of major planning conversations. Could go in `docs/`.
2. **FairClaims domain mapping not done.** Service is live at `fairclaims.onrender.com`; `fairclaims.us` is reserved at the registrar but the DNS record / Render Custom Domain wiring hasn't been completed. Last step before the public link is real.
3. **CEN could adopt the Groq pattern when ready.** FairClaims demonstrated that the existing `openai_compat.py` works as-is against Groq's free tier (`https://api.groq.com/openai/v1`, model `llama-3.3-70b-versatile`). When CEN upgrades to a paid Render plan with persistent disk, switching `CEN_LLM_BACKEND=mock` → `api` with the appropriate `CEN_LLM_API_KEY` + `CEN_LLM_API_BASE` env vars unlocks LLM-grounded synthesis without code changes. Open item #4 in the current state.
4. **No CEN-side improvements blocked or deferred.** This session intentionally did not touch CEN source code. The follow-up items in the Current State above are unchanged from the 2026-04-30 session.

---

### 2026-04-30 — SOP DAG visualization + concierge fixes

**Commits:**
- `fc9ba64` fix(concierge): auto-seed FAQ library + return all owner FAQs when no scope
- `4b29b25` feat(sop): pan/zoom on the draft DAG + clickable issue rows
- `b103442` fix(concierge): keep panel active even when no case is selected
- `93e3076` feat(sop): visual DAG of the draft with issue overlays
- `1a85bad` feat(ux): real buttons + status spinners on every async action
- `c520feb` feat(sop): interactive issue resolution — inline fix proposals + edit endpoints
- `213a0d0` feat(concierge): LLM-grounded conversational guide + persistent 3-panel layout
- `8075adf` feat: SOP ingestion, conversational concierge, navigator dashboard, engine cache

**What was done:**

This was a long, multi-feature session that built out three major capabilities and shipped numerous UX fixes on top.

*SOP-to-DAG ingestion pipeline (`src/cen/sop/`)*
- Parser (`parsers.py`): `python-docx` walker + Markdown passthrough → canonical Markdown.
- Extractor (`extractor.py`): regex-based, targets the DAG-Ready node grammar (NODE/PHASE/TRIGGER/ACTOR/ACTION/OUTPUT/DECISION GATE/NEXT NODE(S)). LLMExtractor protocol slot ready for later.
- Validator (`validators.py`): cycle detection, snake_case ids, branch wiring, reachability, terminal sanity.
- Promoter (`promoter.py`): version bumps (1.0 → 1.1 → ...), refuses drafts with errors, registers a new engine in the live `engines` dict.
- Store (`store.py`): SQLite-backed `sops` table, parsed/extracted/promoted/failed lifecycle.
- Routes: `/sop/upload`, `/sop/{id}/parse`, `/sop/{id}/extract`, `/sop/{id}/promote`.
- Frontend: SOP Studio tab with upload card, SOP list, draft node table, validation summary, promote form.
- Two real SOPs (Proforma + Real Estate) round-trip cleanly. Cycle errors are surfaced; cycles in the Proforma SOP can be cleared by the auto-fix loop.

*SOP interactive issue resolution (`src/cen/sop/fixer.py`)*
- New `ProposedFix` model — every `ValidationIssue` now carries 1-3 fixes with confidence + payload.
- Fix-proposal engine with heuristics for unknown branch targets (closest by edit distance + add-node + drop-edge), cycles (drop back-edge), unreachable (wire from previous + delete), snake_case rename (high confidence), seed branches from NEXT NODE(S).
- New endpoints: `POST /sop/{id}/apply_fix`, `POST /sop/{id}/auto_fix`, `PATCH /sop/{id}/draft/nodes/{node_id}`, `DELETE /sop/{id}/draft/nodes/{node_id}`.
- Frontend `ValidationPanel` renders fixes as inline buttons with per-button spinner ("Applying…").
- "Auto-fix what I can" button applies all confidence-≥-0.9 fixes in one batch (capped at 20 iterations).
- 12 fixer unit tests + 8 editor API tests including a real-Proforma cycle resolution loop.

*SOP visual DAG with issue overlays (`frontend/src/components/sop/DraftDAG.tsx`)*
- Standalone canvas above the validation panel.
- Nodes carry red rings on errors, yellow on warnings, gray strikethrough + reduced opacity on unreachable.
- Cycle edges drawn dashed-red.
- Branches pointing at unknown node ids drawn as dangling red arrows ending in red "?" terminals labeled "true branch" / "false branch".
- Pan/zoom: mouse wheel zooms cursor-anchored, drag to pan, +/− /Fit/1:1 buttons in the header with live percentage.
- Auto-fit on layout change; auto-pan to center the selected node when `selectedNodeId` changes.
- Bidirectional click: node click → SOPStudio sets `selectedNodeId` → ValidationPanel scrolls + bolds matching issue. Issue text click → SOPStudio sets `selectedNodeId` → DAG pans to and highlights the node.
- Selected ring uses accent (blue) over error/warning red/yellow so the selection is always distinguishable.
- Layout primitives extracted to `frontend/src/components/dag/layout.ts` (NODE_COLORS, layoutDAG, edgeAnchors, geometry constants) — usable by future shared canvas refactors.

*Conversational concierge upgrade*
- New `src/cen/prompts/concierge.md` — system prompt template with persona, scope, refusal pattern, 8th-grade reading level, 2-4 sentence ceiling. Tunable as a file.
- New `src/cen/core/concierge_prompt.py` — context-block assembler. Renders case state (workflow + step + collected fields), retrieved chunks, last 6 turns into the prompt. Engine-internal keys filtered.
- LLM-grounded synthesis when backend is non-mock; mock backend skips the LLM call and uses the rule-based fallback (the canned mock output would override grounding).
- Workflow chunks always score 0.95 / 0.85 so case state reliably lands in the top-K.
- Rule-based fallback now leads with case context: *"You're on 'Income verification' right now. Charity care covers patients at or below 200% FPL…"* — much less search-result feel.
- Status-aware `opener_for_case()` + `GET /concierge/opener/{case_id}` — proactive opening message keyed off the case's status. Lands warm before the navigator types.

*Persistent 3-panel layout across all tabs*
- `Layout.tsx` accepts a `rightRail` slot. When present, renders 2-column grid (`[1fr_320px]` on `lg+`).
- App.tsx lifts `activeCase` to App-level state. The Concierge is rendered ONCE at App level via Layout's right rail — it persists across every tab switch with the same active case.
- Executor accepts `initialCaseId` and `onActiveCaseChange` props; pushes its internal activeCase up so the persistent Concierge can read it.
- Concierge active even with no case: input enabled on Dashboard / SOP Studio. Placeholder *"Ask anything from your FAQ library…"*. Backend handles case-less queries (FAQ-only retrieval). Server-side history persistence still requires a case_id (no-case conversations are session-local).

*FAQ library + multi-source retrieval*
- `src/cen/seed/faq_library.md` (200 FAQs from the CEN FAQ Library v2) bundled with the package.
- `seed_default_faqs_if_empty()` runs on app startup; idempotent (only seeds when the table is empty), imports as global FAQs (`owner_id=None`).
- `FAQStore.list_all()` relaxed: when both module_name and project_id are None, drops the scope filter and returns all owner-visible FAQs (instead of "globals only" which returned nothing for the use-case-scoped library).
- Multi-source retriever fuses FAQ + workflow-step + case-context chunks with weighted scoring.
- New `chat_messages` table — append-only history per case_id. `GET /concierge/history/{case_id}` returns the persisted thread.
- New `POST /faqs/import` accepts the markdown library; auto-scopes per use case heading.
- `Concierge.tsx` rewritten to load history on case open + fetch opener in parallel + auto-scroll to bottom on new turn.

*Suggestion extraction (chat → form values)*
- New `src/cen/core/suggestions.py` — `SuggestionExtractor` Protocol + `RegexExtractor` v1 with field-key heuristics (household_size, income, FPL%, ZIP) and type-based fallbacks (boolean/currency/date/select).
- `SuggestedInput` model attached to every `ConciergeResponse`.
- `GET /concierge/suggestions/{case_id}` re-runs extraction over persisted chat.
- Frontend `SuggestionsPanel.tsx` renders confidence-tiered buttons above the form; one-tap "Apply" prefills the field. Existing `provide_input` route remains the only write path (audit chain unbroken).

*Navigator Dashboard + queue endpoint*
- New `src/cen/core/queue.py` — pure-function bucketing logic (6 buckets, mutually exclusive, idle-overrides-non-terminal).
- New `GET /cases/queue` route (registered FIRST on the router so `/queue` doesn't get caught by `/{case_id}`).
- `Session.due_at` field with overdue / due-soon decorations on cards.
- New `SessionStatus.AWAITING_EXTERNAL` for handed-off cases.
- HANDOFF metadata `pause_on_handoff` flag — when true, engine pauses with `awaiting_external:` outcome. Backward compatible: existing 6 modules unchanged.
- New `POST /cases/{id}/resume_external` endpoint.
- `Dashboard.tsx` is the new default tab; renders 6 bucket sections + daily metrics strip + Failed alert.
- Click a card → switches to Executor tab with the case loaded (lifted state via `executorPreselect` in App).
- 18 bucket unit tests + 5 queue API tests + 3 engine HANDOFF tests + 3 resume_external tests.

*Engine cache + decomposition*
- APPROVAL and HANDOFF nodes now cache outputs and replay on resume — closes Non-Negotiable #3.
- Pending APPROVALs no longer go in `executed_nodes`.
- `engine.py` decomposed: 575 → 213 lines. Helpers in `engine_helpers.py` (235), per-node-type runtime handlers in `engine_runtime.py` (301).
- `routes/sessions.py` → `routes/cases.py` rename; `_cases_audit.py`, `_cases_exports.py`, `_cases_actions.py`, `_cases_queue.py` siblings. cases.py 540 → 179 lines.
- `StepCard.tsx` decomposed: 561 → 235; `step_components.tsx` (333).
- `frontend/src/lib/status.ts` + `lib/time.ts` — single source of truth for status labels and `relativeTime` / `dueLabel` helpers.

*Reusable UI primitives + tool-wide spinner pass*
- New `frontend/src/components/ui/Button.tsx` and `Spinner.tsx`.
- SOP Studio: real "Choose a file" button (label + hidden input), multi-stage upload progress ("Uploading… → Reading the document… → Extracting steps…").
- Per-fix-button spinner in ValidationPanel ("Applying…").
- Tool-wide loading labels: Concierge "Thinking…", StepCard "Submitting…" / "Submitting your approval…", SOP "Reading…" / "Re-extracting…" / "Promoting…", Auto-fix "Auto-fixing…".

*CLAUDE.md evolution*
- §1 rewritten with 10 CEN-specific tenets (navigator co-pilot, conversational throughout, multi-source RAG, etc.).
- §4.9 added — file-size discipline + known-monoliths table tracking deferred decompositions.
- §7 rewritten — what stays as `session` (data model, audit column, URL alias) vs what's now `case`.

**Key decisions:**

1. **Mock LLM auto-skips synthesis path** — the canned mock output would override grounding. Rule-based fallback runs for mock; LLM-grounded path runs for `gguf`/`api`. Detected via `backend_name` containing "mock".
2. **Workflow chunks always make top-K** — bumped to 0.95/0.85 score so the case state reliably grounds the LLM regardless of FAQ match strength.
3. **`pause_on_handoff` is opt-in per node** — default false keeps the existing 6 modules' HANDOFF semantics unchanged. New SOPs opt in.
4. **DraftDAG is standalone, no pan/zoom on day one (later added)** — kept simpler; panned/zoomed canvas was a follow-up commit (`4b29b25`) once the basics were in place.
5. **FAQ library auto-seeded as global** — every operator sees them; user-imported FAQs scoped to owner_id are layered on top.
6. **Concierge active without a case** — backend already handled case-less queries; the frontend disabled lock was the only thing in the way. Quick win that unblocked SOP Studio.
7. **Bidirectional DAG ↔ ValidationPanel selection lifted to SOPStudio** — single shared `selectedNodeId` state. Click anywhere → both views update. Auto-pan and auto-scroll close the loop.
8. **`GET /cases/queue` registered before dynamic-param routes** — FastAPI matches by registration order; `/queue` would otherwise be caught by `/{case_id}` and return 404. Documented inline.
9. **Polymorphic Concierge subject deferred** — for v1 the Concierge falls through to FAQ-only mode when no case is selected. SOP-aware mode (with the active SOP draft + issues as context) is its own follow-up PR.

**Files changed:**

*Backend*
- `src/cen/core/engine.py` (decomposed, 575 → 213)
- `src/cen/core/engine_helpers.py` (NEW, 235)
- `src/cen/core/engine_runtime.py` (NEW, 301)
- `src/cen/core/queue.py` (NEW, ~150)
- `src/cen/core/suggestions.py` (NEW, ~330)
- `src/cen/core/concierge.py` (rewritten for LLM + opener; 509)
- `src/cen/core/concierge_prompt.py` (NEW, ~170)
- `src/cen/core/chat_store.py` (NEW)
- `src/cen/core/faq_import.py` (NEW + seed_default_faqs_if_empty)
- `src/cen/core/faq_store.py` (list_all unscoped behavior)
- `src/cen/core/models.py` (added ProposedFix, SuggestedInput, AWAITING_EXTERNAL, due_at, ChatMessage, SOPRecord, ValidationIssue, SourceRef)
- `src/cen/core/session_store.py` (due_at column + migration)
- `src/cen/core/audit_store.py` (get_latest_event_at_for_cases, count_events)
- `src/cen/sop/__init__.py`, `parsers.py`, `extractor.py`, `validators.py`, `fixer.py`, `promoter.py`, `store.py` (NEW package)
- `src/cen/api/routes/cases.py` (renamed from sessions.py)
- `src/cen/api/routes/_cases_audit.py`, `_cases_exports.py`, `_cases_actions.py`, `_cases_queue.py` (NEW)
- `src/cen/api/routes/sop.py` (NEW + apply_fix + auto_fix + node patch/delete)
- `src/cen/api/routes/concierge.py` (LLM dependency + opener route + suggestions route + history route)
- `src/cen/prompts/concierge.md` (NEW)
- `src/cen/seed/faq_library.md` (NEW, 2456 lines, 200 FAQs)

*Frontend*
- `frontend/src/App.tsx` (Dashboard tab default + lifted activeCase + persistent Concierge in rightRail slot)
- `frontend/src/components/Layout.tsx` (rightRail slot + 7xl max-width)
- `frontend/src/components/Concierge.tsx` (history fetch + opener fetch + persistent thread + always-active)
- `frontend/src/components/Executor.tsx` (initialCaseId + onActiveCaseChange + 2-column grid)
- `frontend/src/components/StepCard.tsx` (decomposed; ~235 + step_components.tsx 333)
- `frontend/src/components/Dashboard.tsx` (NEW)
- `frontend/src/components/dashboard/CaseCard.tsx`, `MetricsStrip.tsx` (NEW)
- `frontend/src/components/SOPStudio.tsx` (review pane with DraftDAG + ValidationPanel + selectedNodeId state)
- `frontend/src/components/sop/DraftDAG.tsx` (NEW)
- `frontend/src/components/sop/ValidationPanel.tsx` (NEW; replaces inline ValidationSummary)
- `frontend/src/components/SuggestionsPanel.tsx` (NEW)
- `frontend/src/components/dag/layout.ts` (NEW shared module)
- `frontend/src/components/ui/Button.tsx`, `Spinner.tsx` (NEW)
- `frontend/src/lib/status.ts`, `time.ts` (NEW shared)
- `frontend/src/api.ts` (case_id rename + queue + suggestions + opener + apply_fix + auto_fix + patch_node + delete_node)
- `frontend/src/types.ts` (SessionStatus union + due_at + ProposedFix + ValidationIssue.fixes + QueueCase + QueueMetrics + BucketedQueue + ChatMessage + SuggestedInput)

*Tests* (backend went 247 → 359, +112)
- `tests/sop/` (test_parser, test_extractor_real_sops, test_validator, test_promoter, test_api_lifecycle, test_fixer, test_editor_api)
- `tests/concierge/` (test_faq_import, test_concierge_synthesis, test_concierge_api, test_suggestions)
- `tests/core/test_queue_buckets.py`
- `tests/api/test_queue.py`
- `tests/api/test_resume_external.py`
- `tests/core/test_engine.py` (extended with HANDOFF and APPROVAL caching tests)

*Docs*
- `CLAUDE.md` (§1 rewritten, §4.9 added, §7 rewritten)

**Open items raised:**

1. **SOP-aware Concierge mode** is the obvious next step — when on SOP Studio, the right rail should ground against the active SOP draft + issues, with `suggested_fixes` proposals in chat (in addition to the inline buttons). The plan for this is in the previous turn's response.
2. **`DAGViewer.tsx` (683 lines)** still has its own copy of layout + canvas. The new `dag/layout.ts` is positioned for a follow-up cleanup that drops it under the §4.9 bar.
3. **Persistent prod DB**: `/tmp/cen.db` resets every Render redeploy. FAQ library re-seeds, user FAQs do not. Worth a follow-up to wire a Render persistent disk.
4. **Real LLM in production**: still on `mock` backend. Switching `CEN_LLM_BACKEND=api` with `CEN_LLM_API_BASE` + `CEN_LLM_API_KEY` env vars on Render unlocks the LLM-grounded synthesis path.
5. **GENERATE node type**: appeal letters, dispute letters, charity care applications. Track 2 from earlier — ~4-5 days. Nothing built yet.
6. **CSS line-replacement tooling**: lots of LF→CRLF git warnings on Windows; not a problem for behavior but adds noise.
