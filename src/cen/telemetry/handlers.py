"""Structlog-based telemetry handlers with PII scrubbing."""

from __future__ import annotations

import structlog

from cen.privacy.pii_scrubber import PIIScrubber
from cen.privacy.sanitizer import sanitize_context
from cen.telemetry.events import AOPLoadedEvent, LLMFallbackEvent, WorkflowCompletedEvent

logger = structlog.get_logger()


class TelemetryHandlers:
    """Bundles all event handlers; call register() to wire them to a bus."""

    def __init__(self, scrubber: PIIScrubber) -> None:
        self._scrubber = scrubber

    def register(self, bus: object) -> None:
        from cen.telemetry.bus import AsyncEventBus

        assert isinstance(bus, AsyncEventBus)
        bus.subscribe(WorkflowCompletedEvent, self.on_workflow_completed)
        bus.subscribe(LLMFallbackEvent, self.on_llm_fallback)
        bus.subscribe(AOPLoadedEvent, self.on_aop_loaded)

    async def on_workflow_completed(self, event: WorkflowCompletedEvent) -> None:
        sanitized = sanitize_context(event.context, self._scrubber)
        await logger.ainfo(
            "workflow_completed",
            module=event.module,
            outcome=event.outcome,
            latency=f"{event.latency:.3f}s",
            nodes_executed=event.nodes_executed,
            context_keys=list(sanitized.keys()),
        )

    async def on_llm_fallback(self, event: LLMFallbackEvent) -> None:
        await logger.awarning(
            "llm_fallback",
            primary_backend=event.primary_backend,
            error=event.error,
        )

    async def on_aop_loaded(self, event: AOPLoadedEvent) -> None:
        await logger.ainfo(
            "aop_loaded",
            module=event.module,
            nodes=event.node_count,
            edges=event.edge_count,
        )
