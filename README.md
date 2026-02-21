# CEN AI Concierge

**Community Equity Navigators** — an AOP/DAG workflow engine that routes patients through financial assistance, insurance appeals, benefits enrollment, and community resource pathways.

## Architecture

```
src/cen/
  config.py              # pydantic-settings (CEN_ env prefix)
  core/
    engine.py            # AsyncWorkflowEngine — DAG execution with LLM DI
    models.py            # Pydantic schemas (AOP nodes, edges, workflow I/O)
    aop_parser.py        # JSON → AOPDefinition loader
    exceptions.py        # Domain exceptions
  llm/
    base.py              # LanguageModel Protocol
    mock.py              # Rule-based mock (always available)
    gguf.py              # llama-cpp-python wrapper for local models
    factory.py           # FallbackLanguageModel — timeout → mock fallback
  privacy/
    pii_scrubber.py      # Regex (SSN/phone/email) + optional Presidio NER
    sanitizer.py         # Scrub dicts before telemetry
  telemetry/
    bus.py               # Async EventBus (observer pattern)
    events.py            # WorkflowCompleted, LLMFallback, AOPLoaded
    handlers.py          # structlog handlers with PII scrubbing
  api/
    app.py               # create_app() factory
    dependencies.py      # FastAPI Depends() providers
    routes/              # /execute, /update-aop, /tlm/generate, /health, /ready
    middleware/           # X-Request-ID, global error → JSON
  modules/               # 5 AOP workflow definitions (JSON)
```

## AOP Modules

| Module | Description |
|--------|-------------|
| **Charity Care Navigator** | Routes patients by FPL income to charity care or debt cancellation |
| **Debt Cancellation Engine** | Audits bills for duplicates and NSA violations, generates disputes |
| **Insurance Appeal Assistant** | Classifies denials with 3-way branching (medical necessity / coding / general) |
| **Benefits Enrollment Navigator** | Medicaid → ACA → CHIP eligibility cascade |
| **Community Resource Router** | Sequential screening for housing, food, and transportation needs |

## Setup

```bash
# Install in dev mode
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
```

## Running

```bash
# Start with mock LLM (default)
CEN_LLM_BACKEND=mock uvicorn cen.api.app:create_app --factory --reload

# Start with local GGUF model
CEN_LLM_BACKEND=gguf CEN_GGUF_MODEL_PATH=./models/model.gguf uvicorn cen.api.app:create_app --factory --reload
```

## API

```bash
# Liveness check
curl http://localhost:8000/health

# Readiness (loaded modules + LLM status)
curl http://localhost:8000/ready

# Execute a workflow
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"module_name":"charity_care_navigator","context":{"income_fpl_percent":150}}'

# Register/update an AOP module at runtime
curl -X POST http://localhost:8000/update-aop \
  -H "Content-Type: application/json" \
  -d @src/cen/modules/debt_cancellation_engine.json

# Generate text via LLM
curl -X POST http://localhost:8000/tlm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Check income eligibility","max_tokens":128}'
```

## Testing

```bash
pytest tests/ -v
```

## Configuration

All settings use the `CEN_` env prefix. See `.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `CEN_LLM_BACKEND` | `mock` | `mock` or `gguf` |
| `CEN_GGUF_MODEL_PATH` | `./models/model.gguf` | Path to GGUF model file |
| `CEN_LLM_TIMEOUT` | `10.0` | Seconds before falling back to mock |
| `CEN_CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |
| `CEN_LOG_RENDERER` | `console` | `console` (dev) or `json` (prod) |
| `CEN_PII_BACKEND` | `regex` | `regex` or `presidio` |

## Optional Dependencies

```bash
# Local GGUF model support
pip install -e ".[llm]"

# Presidio NER-based PII scrubbing
pip install -e ".[privacy]"
```
