"""Global exception handler — maps domain exceptions to structured JSON."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import structlog

from cen.core.exceptions import CENError, CycleDetectedError, ModuleNotFoundError

logger = structlog.get_logger()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ModuleNotFoundError)
    async def module_not_found(request: Request, exc: ModuleNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "available": exc.available},
        )

    @app.exception_handler(CycleDetectedError)
    async def cycle_detected(request: Request, exc: CycleDetectedError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    @app.exception_handler(CENError)
    async def cen_error(request: Request, exc: CENError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        await logger.aexception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
