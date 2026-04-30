"""Application factory — wires all components together."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cen.config import Settings
from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.core.artifact_store import ArtifactStore
from cen.core.audit_store import AuditStore
from cen.core.chat_store import ChatMessageStore
from cen.core.faq_store import FAQStore
from cen.core.project_store import ProjectStore
from cen.core.session_store import SessionStore
from cen.llm.factory import create_language_model
from cen.sop.store import SOPStore
from cen.storage import LocalDiskStorage
from cen.privacy.pii_scrubber import create_scrubber
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.handlers import AuditHandlers, TelemetryHandlers
from cen.api.dependencies import init_dependencies
from cen.api.middleware.error_handler import register_error_handlers
from cen.api.middleware.request_id import RequestIDMiddleware
from cen.api.routes import artifacts, auth, concierge, health, llm, modules, workflows
from cen.api.routes import cases, projects, sop

logger = structlog.get_logger()


def _configure_structlog(settings: Settings) -> None:
    renderer: structlog.types.Processor
    if settings.log_renderer == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _enforce_deployment_mode(settings: Settings) -> None:
    """Refuse to start in production mode if hardening prerequisites are not met.

    v1 ships with `deployment_mode=synthetic` by default. The synthetic
    mode is for development against fake data — it places no
    restrictions on the LLM backend and shows a loud banner in the UI.

    `deployment_mode=production` is the operator's explicit attestation
    that the deployment is going to receive real PHI. In that mode:
    - The `api` LLM backend is only allowed if `llm_baa_confirmed=True`
      (the operator has signed a Business Associate Agreement with the
      provider). Otherwise startup fails — better a hard error than
      silently leaking PHI to a non-BAA'd third party.
    - `mock` and `gguf` (local) backends are always allowed.
    """
    if settings.deployment_mode == "production" and settings.llm_backend == "api":
        if not settings.llm_baa_confirmed:
            raise RuntimeError(
                "CEN_DEPLOYMENT_MODE=production requires CEN_LLM_BAA_CONFIRMED=true "
                "when CEN_LLM_BACKEND=api. Either sign a BAA with your LLM provider "
                "and set CEN_LLM_BAA_CONFIRMED=true, or switch to a local backend "
                "(CEN_LLM_BACKEND=gguf|mock)."
            )


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    _enforce_deployment_mode(settings)
    _configure_structlog(settings)

    # Stores — created here, init/close via lifespan.
    session_store = SessionStore(settings.db_path)
    project_store = ProjectStore(settings.db_path)
    audit_store = AuditStore(settings.db_path)
    artifact_store = ArtifactStore(settings.db_path)
    faq_store = FAQStore(settings.db_path)
    chat_store = ChatMessageStore(settings.db_path)
    sop_store = SOPStore(settings.db_path)
    storage_backend = LocalDiskStorage(settings.uploads_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Ensure data directory exists (skip for :memory:)
        if settings.db_path != ":memory:":
            Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        await session_store.initialize()
        await project_store.initialize()
        await audit_store.initialize()
        await artifact_store.initialize()
        await faq_store.initialize()
        await chat_store.initialize()
        await sop_store.initialize()
        yield
        await sop_store.close()
        await chat_store.close()
        await faq_store.close()
        await artifact_store.close()
        await audit_store.close()
        await project_store.close()
        await session_store.close()

    app = FastAPI(
        title="CEN AI Concierge",
        description="Community Equity Navigators — AOP/DAG Business Logic Platform",
        version="0.2.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    register_error_handlers(app)

    # Core services
    llm_instance = create_language_model(settings)
    event_bus = AsyncEventBus()
    scrubber = create_scrubber(settings.pii_backend)
    telemetry = TelemetryHandlers(scrubber)
    telemetry.register(event_bus)
    audit_handlers = AuditHandlers(audit_store, scrubber)
    audit_handlers.register(event_bus)

    # Shared semaphore for LLM concurrency
    llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    # Load modules
    engines: dict[str, AsyncWorkflowEngine] = {}
    modules_dir = Path(__file__).resolve().parent.parent / "modules"
    if modules_dir.exists():
        for aop_file in sorted(modules_dir.glob("*.json")):
            try:
                aop = load_aop_from_file(aop_file)
                engine = AsyncWorkflowEngine(
                    llm=llm_instance,
                    event_bus=event_bus,
                    llm_semaphore=llm_semaphore,
                )
                engine.load_aop(aop)
                engines[aop.module_name] = engine
                structlog.get_logger().info(
                    "module_loaded", module=aop.module_name, file=aop_file.name
                )
            except Exception:
                structlog.get_logger().exception(
                    "module_load_failed", file=aop_file.name
                )

    # Dependency injection
    init_dependencies(
        settings, engines, llm_instance,
        session_store=session_store,
        project_store=project_store,
        audit_store=audit_store,
        artifact_store=artifact_store,
        faq_store=faq_store,
        chat_store=chat_store,
        sop_store=sop_store,
        storage_backend=storage_backend,
        event_bus=event_bus,
        llm_semaphore=llm_semaphore,
    )

    # Routes
    app.include_router(workflows.router)
    app.include_router(llm.router)
    app.include_router(health.router)
    app.include_router(auth.router)
    # Mount the cases router twice — /cases (canonical, per CLAUDE.md
    # §7) and /sessions (legacy alias for backward compatibility).
    # Same handlers, same store.
    app.include_router(cases.router, prefix="/cases", tags=["cases"])
    app.include_router(cases.router, prefix="/sessions", tags=["sessions"])
    app.include_router(projects.router)
    app.include_router(artifacts.router)
    app.include_router(concierge.router)
    app.include_router(modules.router)
    app.include_router(sop.router)

    # Serve frontend static files (production)
    # Check relative path (local dev) then absolute path (Docker)
    static_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if not static_dir.exists():
        static_dir = Path("/app/frontend/dist")
    if static_dir.exists():
        index_html = static_dir / "index.html"

        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(str(index_html))

        # Mount full static dir last — catches assets and unknown paths
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")

    return app
