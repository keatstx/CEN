from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    ACTION = "ACTION"
    CONDITION = "CONDITION"
    HANDOFF = "HANDOFF"


class NodeMetadata(BaseModel):
    label: str = ""
    description: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)


class AOPNode(BaseModel):
    id: str
    type: NodeType
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)
    condition_field: Optional[str] = None
    condition_operator: Optional[str] = None
    condition_value: Optional[Any] = None
    true_next: Optional[str] = None
    false_next: Optional[str] = None


class AOPEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class AOPDefinition(BaseModel):
    module_name: str
    version: str = "1.0"
    description: str = ""
    nodes: List[AOPNode]
    edges: List[AOPEdge]


class WorkflowInput(BaseModel):
    module_name: str
    context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    module_name: str
    executed_nodes: List[str]
    final_outcome: str
    context: Dict[str, Any]


class TelemetryEvent(BaseModel):
    module: str
    outcome: str
    latency: str
    nodes_executed: int
