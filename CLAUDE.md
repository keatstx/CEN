# CEN — Community Equity Navigators

AI Concierge platform for No Surprises Act compliance. Executes AOP/DAG workflows to guide patients through charity care, benefits enrollment, insurance appeals, debt cancellation, and community resource navigation.

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI (Python 3.9+) |
| Database | SQLite via aiosqlite |
| Workflow Engine | NetworkX DAG execution |
| LLM | Pluggable (mock / GGUF) |
| Privacy | PII scrubbing (regex / Presidio) |
| Logging | structlog |
| Frontend | React (Vite, port 5173) |

## Project Structure

```
src/cen/
├── api/              # FastAPI app, routes, dependencies, middleware
│   └── routes/       # health, sessions, workflows, llm
├── core/             # Engine, models, session store, audit store
├── llm/              # Language model backends (mock, gguf)
├── modules/          # AOP workflow definitions (JSON)
├── privacy/          # PII scrubber, context sanitizer
└── telemetry/        # Event bus, event types, handlers
tests/
├── api/              # API integration tests
├── core/             # Engine, store unit tests
├── llm/              # LLM factory tests
├── modules/          # Module validation tests
└── privacy/          # PII scrubber tests
```

## Quick Commands

```bash
# Run all tests
pytest tests/ -v

# Run API server
uvicorn cen.api.app:create_app --factory --reload --port 8000

# Run specific test file
pytest tests/core/test_engine.py -v
```

## Configuration

Environment variables prefixed with `CEN_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CEN_LLM_BACKEND` | `mock` | LLM backend (`mock` or `gguf`) |
| `CEN_DB_PATH` | `./data/cen.db` | SQLite database path |
| `CEN_PII_BACKEND` | `regex` | PII scrubber (`regex` or `presidio`) |
| `CEN_LOG_RENDERER` | `console` | Log format (`console` or `json`) |

## Testing

- Tests use `db_path=":memory:"` — no file cleanup needed
- `pytest-asyncio` with `asyncio_mode = "auto"` — all async tests run automatically
- API tests use `httpx.AsyncClient` with `ASGITransport` (no server needed)

## Key Patterns

- **Event Bus**: `AsyncEventBus` (pub/sub) for telemetry and audit. Handlers subscribe to dataclass event types.
- **Session Store**: SQLite-backed CRUD for workflow sessions (async via aiosqlite).
- **Audit Store**: Append-only SQLite table for compliance-grade audit trail. No update/delete by design.
- **PII Scrubbing**: All context data is scrubbed before audit persistence or telemetry emission.
- **AOP Modules**: JSON workflow definitions loaded at startup from `src/cen/modules/`.

## Git Commits

Only commit when explicitly asked. Use conventional commit format (`feat:`, `fix:`, `refactor:`, etc.).

## Skills

| Skill | Purpose |
|-------|---------|
| `/commit` | Stage and commit with conventional message |
| `/summarize` | Summarize session work and decisions |
