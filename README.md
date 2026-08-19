# CEN — Community Equity Navigators

An AI Concierge platform for No Surprises Act compliance and patient financial advocacy. CEN executes human-authored **AOP/DAG workflows** that guide navigators (and, later, patients) through charity care, benefits enrollment, insurance appeals, debt cancellation, and community-resource navigation — while producing a defensible, append-only audit trail for every outcome.

- **Live:** https://cen-48pm.onrender.com
- **Deploy:** Render (single Docker service — FastAPI serves the built frontend)

## What it does

A FastAPI + React app with a three-panel **FlowUX** shell (left nav · center Studio · persistent AI Concierge) and five surfaces:

| Surface | What a navigator does |
|---|---|
| **Home / Dashboard** | Bucketed case queue (needs input / waiting on patient / pending approval / done) + metrics. |
| **Executor** | Work a case: guided Step Cards, document upload, approval gates, rewind, "Information so far", **generated documents**, and **repeating-step (loop) status**. |
| **Workflow Map** | Read-only pan/zoom DAG viewer of any workflow. |
| **SOP Studio** | Upload a `.docx`/`.pdf` SOP → parsed → extracted draft workflow → validate → fix → **tag** → promote to a runnable workflow. |
| **Concierge** | Persistent right rail. Multi-source retrieval (FAQ library + current step + case history), citations, step-scoped FAQ, suggested inputs, hard medical/legal/financial guardrails. |

Six built-in workflows ship in `src/cen/modules/`: `master_case_orchestrator`, `charity_care_navigator`, `insurance_appeal_assistant`, `benefits_enrollment_navigator`, `debt_cancellation_engine`, `community_resource_router`.

## Engine

`AsyncWorkflowEngine` loads an `AOPDefinition` (nodes + edges) and executes it.

- **Four node types:** `ACTION`, `CONDITION`, `HANDOFF`, `APPROVAL`. Document production is an ACTION subtype (`metadata.action_kind == "generate"`) — no fifth type.
- **Bounded loops (LDCG):** a strongly-connected region closed by a `loop_back` edge repeats up to `max_iterations`, checks an exit condition each pass, and escalates to a human gate (`on_limit_next`) when the cap is hit. Pure DAGs take an unchanged topological fast path; unannotated cycles are still rejected.
- **Idempotent resume (Non-Negotiable #3):** per-node output cache in `context["__node_outputs"]` (namespaced per iteration inside loops) means side-effecting nodes fire exactly once per pass, never re-firing on resume.
- **Pause states:** `AWAITING_INPUT`, `AWAITING_APPROVAL`, `AWAITING_EXTERNAL`.

## Architecture

```
src/cen/
  config.py              # pydantic-settings (CEN_ env prefix)
  core/
    engine.py            # AsyncWorkflowEngine (thin dispatcher)
    engine_runtime.py    # per-node-type handlers + ExecutionState
    engine_helpers.py    # condition eval, input derivation, branch skip
    engine_loops.py      # bounded loop regions (LDCG)
    engine_generate.py   # GENERATE (document production) handler
    models.py            # Pydantic schemas (AOP, session, concierge, ...)
    aop_parser.py        # JSON → AOPDefinition
    session_store.py / project_store.py / audit_store.py
    artifact_store.py / chat_store.py / faq_store.py    # aiosqlite stores
    concierge*.py        # multi-source retrieval + prompt builder
    faq_import.py / faq_classify.py / tags.py           # FAQ + tag tooling
    queue.py / proactive.py / suggestions.py
  llm/                   # LanguageModel Protocol: mock | gguf | openai_compat
  privacy/               # PII scrubber (regex default, Presidio optional) + sanitizer
  telemetry/             # AsyncEventBus + audit/telemetry handlers
  sop/                   # parsers / extractor / validators / fixer / promoter / store
  storage/               # LocalDiskStorage adapter
  prompts/  seed/        # concierge prompt; FAQ library + tag vocabulary seeds
  modules/               # 6 built-in AOP workflow definitions (JSON)
  api/
    app.py               # create_app() factory
    dependencies.py      # FastAPI Depends() providers
    routes/              # cases, projects, artifacts, concierge, sop, modules,
                         #   workflows, auth, me, llm (tlm), health
frontend/src/            # React 19 + Vite + TS + Tailwind (state via App-level hooks)
```

## LLM backends — `CEN_LLM_BACKEND`

| Backend | Use | PHI safe? |
|---|---|---|
| `mock` | tests / dev without a model (default) | yes (no network) |
| `gguf` | local llama.cpp | yes (no network) |
| `api` | OpenAI-compatible endpoint (Ollama, vLLM, hosted) | **only with a signed BAA** |

Production runs `api` against Groq. `CEN_LLM_MODEL` is an ordered preference list (`openai/gpt-oss-20b,openai/gpt-oss-120b`) — the first model the provider still offers is resolved automatically, so a retired model costs one failed call instead of an outage. Groq retires models on a published schedule, so check [their deprecations page](https://console.groq.com/docs/deprecations) when `/ready` reports `llm_available: false`. New providers go behind the `LanguageModel` Protocol — never call third-party SDKs from routes/services. When `deployment_mode=production`, the `api` backend requires `CEN_LLM_BAA_CONFIRMED=true` or the app refuses to start.

## Setup

```bash
pip install -e ".[dev]"          # backend
cd frontend && npm install       # frontend
```

## Running

```bash
# Backend (mock LLM by default) — serves the built frontend if present
uvicorn cen.api.app:create_app --factory --reload --port 8000

# Frontend dev server (hot reload, proxies the API)
cd frontend && npm run dev       # http://localhost:5173

# Local hosted LLM (OpenAI-compatible)
CEN_LLM_BACKEND=api CEN_LLM_API_BASE=http://localhost:11434/v1 \
CEN_LLM_MODEL=llama3 uvicorn cen.api.app:create_app --factory --reload
```

## Testing

```bash
pytest tests/ -v                 # backend
mypy src/cen                     # type check
cd frontend && npx tsc -b && npm run lint && npm run build
```

## Configuration

All settings use the `CEN_` env prefix.

| Variable | Default | Description |
|---|---|---|
| `CEN_LLM_BACKEND` | `mock` | `mock` \| `gguf` \| `api` |
| `CEN_LLM_API_BASE` / `CEN_LLM_MODEL` / `CEN_LLM_API_KEY` | — | OpenAI-compatible endpoint config (`api` backend) |
| `CEN_GGUF_MODEL_PATH` | `./models/model.gguf` | GGUF model path (`gguf` backend) |
| `CEN_LLM_TIMEOUT` | `10.0` | Seconds before falling back to mock |
| `CEN_DB_PATH` | `./data/cen.db` | SQLite path (`:memory:` in tests) |
| `CEN_PII_BACKEND` | `regex` | `regex` \| `presidio` |
| `CEN_DEPLOYMENT_MODE` | `synthetic` | `synthetic` \| `production` (gates the BAA check) |
| `CEN_OPERATOR_PASSWORD` / `CEN_ADMIN_OPERATORS` | — | prototype auth + admin allowlist |

## Optional dependencies

```bash
pip install -e ".[llm]"          # local GGUF support (llama-cpp-python)
pip install -e ".[privacy]"      # Presidio NER-based PII scrubbing
```

See `CLAUDE.md` for engineering standards, non-negotiables, and the verification process.
