"""Async EventBus — lightweight observer pattern for telemetry."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine


EventHandler = Callable[..., Coroutine[Any, Any, None]]


class AsyncEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def emit(self, event: object) -> None:
        handlers = self._handlers.get(type(event), [])
        if handlers:
            await asyncio.gather(*(h(event) for h in handlers))
