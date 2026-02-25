"""Application factory — wires all components together."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cen.config import Settings
from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.core.audit_store import AuditStore
from cen.core.session_store import SessionStore
from cen.llm.factory import create_language_model
from cen.privacy.pii_scrubber import create_scrubber
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.handlers import AuditHandlers, TelemetryHandlers
from cen.api.dependencies import init_dependencies
from cen.api.middleware.error_handler import register_error_handlers
from cen.api.middleware.request_id import RequestIDMiddleware
from cen.api.routes import health, llm, modules, workflows
from cen.api.routes import sessions

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


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    _configure_structlog(settings)

    # Session store + audit store — created here, initialized/closed via lifespan
    session_store = SessionStore(settings.db_path)
    audit_store = AuditStore(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Ensure data directory exists (skip for :memory:)
        if settings.db_path != ":memory:":
            Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        await session_store.initialize()
        await audit_store.initialize()
        yield
        await audit_store.close()
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
        audit_store=audit_store,
        event_bus=event_bus,
    )

    # Routes
    app.include_router(workflows.router)
    app.include_router(llm.router)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(modules.router)

    return app
