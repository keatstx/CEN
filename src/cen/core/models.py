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


class SourceRef(BaseModel):
    """Back-pointer from an AOP node to the SOP it was extracted from.

    Set by the SOP ingestion pipeline so the UI can offer a "see source"
    affordance and the audit trail records provenance for every
    auto-generated node. Mirrors Non-Negotiable #6 (provenance on AI
    output) for the authoring side, not just runtime.
    """

    sop_id: str
    section: str = ""           # human label, e.g. "Part I, NODE: PF-01"
    page: Optional[int] = None
    excerpt: str = ""           # first ~200 chars of the source paragraph


class NodeMetadata(BaseModel):
    label: str = ""
    description: str = ""
    # SOP-derived fields (all optional, populated by the ingestion
    # pipeline when a node is extracted from a Standard Operating
    # Procedure document). Hand-authored modules typically leave them
    # null. They are display metadata only — they do not change engine
    # behavior. `parallel` records that the SOP author marked the node
    # as concurrent-safe; the engine still serializes execution.
    actor: Optional[str] = None
    trigger: Optional[str] = None
    output: Optional[str] = None
    timeline: Optional[str] = None
    parallel: bool = False
    source_ref: Optional[SourceRef] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Optional[List[InputField]] = None
    # auto_set: declarative "after this node finishes, write these
    # values into context". Used to bridge ACTION → CONDITION gaps:
    # e.g. document_intake's auto_set sets documents_complete=true so
    # the downstream documents_complete CONDITION reads true and
    # advances without auto-pausing for a redundant boolean question.
    # Applies after first execution of an ACTION and after a successful
    # APPROVAL. Cached on resume so the values persist across re-runs.
    auto_set: Optional[Dict[str, Any]] = None


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
    source_doc: Optional[str] = None  # sop_id when extracted from an SOP
    nodes: List[AOPNode]
    edges: List[AOPEdge]


class ValidationIssue(BaseModel):
    severity: str  # "error" | "warning" | "info"
    node_id: Optional[str] = None
    message: str


class SOPRecord(BaseModel):
    """An uploaded Standard Operating Procedure document.

    The bytes live in the StorageBackend keyed by `storage_key`; this
    model is the database row that tracks parsing/extraction state and
    links the eventual promoted module back to its source.
    """

    id: str
    filename: str
    content_type: str = ""
    size: int = 0
    storage_key: str = ""
    status: str = "uploaded"  # uploaded | parsed | extracted | promoted | failed
    canonical_md: Optional[str] = None
    draft_module: Optional[AOPDefinition] = None
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    promoted_module_name: Optional[str] = None
    promoted_module_version: Optional[str] = None
    owner_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


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
    AWAITING_EXTERNAL = "AWAITING_EXTERNAL"  # handed off, waiting on a third party
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
    # ISO datetime when the case is due. Optional; None means no
    # deadline. Surfaced on the dashboard as is_due_soon / is_overdue
    # decorations on case cards.
    due_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class ProvideInputRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)


class FAQ(BaseModel):
    """One Q+A pair in the concierge knowledge base.

    FAQs are scoped by `module_name` (workflow-specific FAQs) or
    `project_id` (case-specific FAQs) — when both are NULL the FAQ is
    global. The concierge retrieval prefers more-specific matches.
    """

    id: str
    module_name: Optional[str] = None
    project_id: Optional[str] = None
    question: str
    answer: str
    source_filename: str = ""
    owner_id: Optional[str] = None
    created_at: str = ""


class FAQCreate(BaseModel):
    question: str
    answer: str
    module_name: Optional[str] = None
    project_id: Optional[str] = None
    source_filename: str = ""


class ConciergeQuery(BaseModel):
    question: str
    case_id: Optional[str] = None
    current_node_id: Optional[str] = None


class ConciergeCitation(BaseModel):
    """One grounding source used to answer a question.

    `kind` distinguishes where the chunk came from so the UI can render
    them differently — FAQs link to the FAQ admin, workflow citations
    link to the step in the DAG, SOP citations open the source SOP.
    """

    faq_id: Optional[str] = None
    kind: str = "faq"  # faq | workflow | sop | case_context
    question: str = ""
    score: float = 0.0
    node_id: Optional[str] = None
    sop_id: Optional[str] = None


class SuggestedInput(BaseModel):
    """A structured value the concierge extracted from chat that the
    navigator can apply to the current step's form with one tap.

    Suggestions never write to context directly — the UI surfaces them
    above the form, the navigator clicks "Apply", and the existing
    `provide_input` route is what actually advances the workflow. That
    keeps the audit chain unbroken (Non-Negotiable #2).
    """

    key: str
    value: Any
    confidence: float = 0.0  # 0..1, surfaced as a tier in the UI
    evidence: str = ""       # short excerpt from the chat
    source: str = "chat"     # chat | sop | case_history (future)


class ConciergeResponse(BaseModel):
    answer: str
    mode: str  # "lookup" | "synthesis" | "guardrail" | "no_match"
    citations: List[ConciergeCitation] = Field(default_factory=list)
    suggested_inputs: List[SuggestedInput] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """One persisted turn in a case's concierge thread.

    Append-only — the chat history is part of the audit trail. Updates
    happen via redaction, never row deletion.
    """

    id: str
    case_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    citations: List[ConciergeCitation] = Field(default_factory=list)
    mode: str = ""
    owner_id: Optional[str] = None
    created_at: str = ""


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
    due_at: Optional[str] = None


class SessionUpdate(BaseModel):
    context: Optional[Dict[str, Any]] = None
    status: Optional[SessionStatus] = None
    name: Optional[str] = None
    due_at: Optional[str] = None
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
