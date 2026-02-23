"""Pydantic data models for the AOP/DAG system."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    ACTION = "ACTION"
    CONDITION = "CONDITION"
    HANDOFF = "HANDOFF"
    APPROVAL = "APPROVAL"


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


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Session(BaseModel):
    id: str
    module_name: str
    status: SessionStatus = SessionStatus.ACTIVE
    context: Dict[str, Any] = Field(default_factory=dict)
    executed_nodes: List[str] = Field(default_factory=list)
    pending_node: Optional[str] = None
    approved_nodes: List[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class SessionCreate(BaseModel):
    module_name: str
    context: Dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    context: Optional[Dict[str, Any]] = None
    status: Optional[SessionStatus] = None


class LLMGenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 128


class LLMGenerateResponse(BaseModel):
    response: str
    backend: str


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    modules_loaded: List[str]
    llm_backend: str
    llm_available: bool


class AuditEntry(BaseModel):
    id: int
    session_id: str
    module: str
    node_id: str
    node_type: str
    outcome: str
    context: Dict[str, Any]
    timestamp: str
    record_hash: str = ""


class AuditVerification(BaseModel):
    is_valid: bool
    last_verified_id: int
    total_records: int
    verified_at: str
