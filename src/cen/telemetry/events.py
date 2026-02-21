"""Telemetry event dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowCompletedEvent:
    module: str
    outcome: str
    latency: float
    nodes_executed: int
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMFallbackEvent:
    primary_backend: str
    error: str


@dataclass(frozen=True)
class AOPLoadedEvent:
    module: str
    node_count: int
    edge_count: int


@dataclass(frozen=True)
class NodeExecutedEvent:
    session_id: str
    module: str
    node_id: str
    node_type: str
    outcome: str
    timestamp: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalEvent:
    session_id: str
    module: str
    node_id: str
    timestamp: str
