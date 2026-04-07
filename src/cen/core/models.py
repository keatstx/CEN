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


class InputField(BaseModel):
    """One field that the user must provide before a step can execute.

    Used in two ways:
    - Declarative: an ACTION node's metadata.input_schema lists fields
      the author wants to prompt for (e.g. file uploads, currency,
      typed dropdowns).
    - Auto-derived: the engine generates an InputField on the fly when
      a CONDITION node's condition_field is missing from context.

    The frontend renders these into form controls in the new
    three-frame Executor's middle pane.
    """

    key: str
    label: str = ""
    type: str = "text"  # text | number | currency | boolean | date | select | file
    required: bool = True
    options: Optional[List[Dict[str, str]]] = None  # for type=select
    description: str = ""


class NodeMetadata(BaseModel):
    label: str = ""
    description: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Optional[List[InputField]] = None


class AOPNode(BaseModel):
    id: str
    type: NodeType
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)
    condition_field: Optional[str] = None
    condition_operator: Optional[str] = None
    condition_value: Optional[Any] = None
    condition_value_field: Optional[str] = None
    true_next: Optional[str] = None
    false_next: Optional[str] = None
    branches: Optional[Dict[str, str]] = None


class AOPEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class AOPDefinition(BaseModel):
    model_config = {"extra": "ignore"}
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
    pending_node: Optional[str] = None
    pending_input_fields: Optional[List[InputField]] = None


class User(BaseModel):
    """Operator identity returned by the auth dependency.

    v1 is single-operator with a stub user. When real auth lands, this
    becomes the authenticated user from the JWT/session token. The
    `id` field is what gets stored in `Session.owner_id` and
    `Project.owner_id` so the multi-tenant enforcement hook is in place
    from day one.
    """

    id: str
    name: str = ""


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Project(BaseModel):
    """A project represents a patient (or matter) under which one or more
    cases run. Demographics, identity documents, insurance cards, and
    consent live at the project level and flow into every case below it.

    v1 stores projects but does not yet expose them in the UI; new cases
    auto-attach to a default project per owner. The full project picker
    lands in step 4 of the foundation roadmap.
    """

    id: str
    name: str
    description: str = ""
    owner_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_INPUT = "AWAITING_INPUT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Session(BaseModel):
    id: str
    module_name: str
    module_version: str = "1.0"
    name: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    context: Dict[str, Any] = Field(default_factory=dict)
    executed_nodes: List[str] = Field(default_factory=list)
    pending_node: Optional[str] = None
    pending_input_fields: Optional[List[InputField]] = None
    approved_nodes: List[str] = Field(default_factory=list)
    owner_id: Optional[str] = None
    project_id: Optional[str] = None
    version: int = 1
    created_at: str = ""
    updated_at: str = ""


class ProvideInputRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    """Metadata for a file uploaded against a case (and optionally a step).

    The actual file bytes live in the StorageBackend keyed by
    `storage_key`; this model is the database row that links it to the
    case and tracks the user-facing properties.
    """

    id: str
    case_id: str
    project_id: Optional[str] = None
    node_id: Optional[str] = None
    filename: str
    content_type: str
    size: int
    storage_key: str
    owner_id: Optional[str] = None
    uploaded_at: str = ""


class SessionCreate(BaseModel):
    module_name: str
    context: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None
    project_id: Optional[str] = None


class SessionUpdate(BaseModel):
    context: Optional[Dict[str, Any]] = None
    status: Optional[SessionStatus] = None
    name: Optional[str] = None
    expected_version: Optional[int] = None


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
    deployment_mode: str = "synthetic"


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
