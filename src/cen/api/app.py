"""Application factory — wires all components together."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cen.config import Settings
from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.llm.factory import create_language_model
from cen.privacy.pii_scrubber import create_scrubber
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.handlers import TelemetryHandlers
from cen.api.dependencies import init_dependencies
from cen.api.middleware.error_handler import register_error_handlers
from cen.api.middleware.request_id import RequestIDMiddleware
from cen.api.routes import health, llm, workflows

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

    app = FastAPI(
        title="CEN AI Concierge",
        description="Community Equity Navigators — AOP/DAG Business Logic Platform",
        version="0.2.0",
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

    # Load modules
    engines: dict[str, AsyncWorkflowEngine] = {}
    modules_dir = Path(__file__).resolve().parent.parent / "modules"
    if modules_dir.exists():
        for aop_file in sorted(modules_dir.glob("*.json")):
            try:
                aop = load_aop_from_file(aop_file)
                engine = AsyncWorkflowEngine(llm=llm_instance, event_bus=event_bus)
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
    init_dependencies(settings, engines, llm_instance)

    # Routes
    app.include_router(workflows.router)
    app.include_router(llm.router)
    app.include_router(health.router)

    return app
