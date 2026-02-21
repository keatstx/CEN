# CEN Engine — Identified Shortcomings & Progress

## Original Shortcomings

| Component | Why it matters | Difficulty | Status |
|---|---|---|---|
| Persistent Storage | Saves progress if the app crashes mid-workflow | Medium (SQLite) | Done |
| Schema Validation | Ensures LLM output is actually a number, not a sentence | Easy (Pydantic) | Done |
| Concurrency Limits | Prevents the DAG from running 5 LLMs at once | Hard (Semaphores) | Not started |
| Logging/Audit Trail | Essential for "No Surprises Act" legal compliance | Easy (AOP Aspect) | Partial |

### Persistent Storage (Done)
- SQLite-backed `SessionStore` via `aiosqlite` (`src/cen/core/session_store.py`)
- Sessions persist context, executed nodes, and status across requests
- `POST /sessions` CRUD endpoints for lifecycle management

### Schema Validation (Done)
- Pydantic models enforce structure on all inputs and outputs (`src/cen/core/models.py`)
- `AOPNode`, `WorkflowInput`, `Session`, `WorkflowResult`, etc.

### Concurrency Limits (Not started)
- No semaphore or throttling on parallel LLM calls
- Needs implementation to prevent resource exhaustion

### Logging/Audit Trail (Partial)
- `structlog` for structured logging
- `AsyncEventBus` emits `WorkflowCompletedEvent` with outcome, latency, and context
- Not yet a full compliance-grade audit trail for legal requirements

---

## Approval Gates (New Feature)

Built on top of persistent storage. Adds human review checkpoints where workflows pause and wait for explicit approval before continuing. This is a new capability, not one of the four shortcomings above.

### Completed Tasks

1. **Add APPROVAL node type and session fields to models** (`src/cen/core/models.py`)
   - Added `APPROVAL` to `NodeType` enum
   - Added `AWAITING_APPROVAL` to `SessionStatus` enum
   - Added `pending_node` and `approved_nodes` fields to `Session` model

2. **Handle APPROVAL nodes in the engine** (`src/cen/core/engine.py`)
   - Added `approved_nodes` parameter to `execute()`
   - APPROVAL nodes break execution early if unapproved, or pass through if approved

3. **Persist new session fields in the store** (`src/cen/core/session_store.py`)
   - Added `pending_node` and `approved_nodes` columns to the sessions table
   - Updated `_row_to_session()`, `create()`, and `update()` to handle new fields

4. **Add approval-specific error** (`src/cen/core/exceptions.py`)
   - Added `ApprovalNotPendingError` for approving a session not in `AWAITING_APPROVAL` status

5. **Handle new exception in error handler** (`src/cen/api/middleware/error_handler.py`)
   - Added 409 (Conflict) handler for `ApprovalNotPendingError`

6. **Update /execute route for approval stops** (`src/cen/api/routes/workflows.py`)
   - Detect `pending_approval:` outcomes and save session as `AWAITING_APPROVAL`
   - Pass `approved_nodes` to `engine.execute()` when a session is provided

7. **Add POST /sessions/{id}/approve endpoint** (`src/cen/api/routes/sessions.py`)
   - Validates session exists and is `AWAITING_APPROVAL`
   - Marks the pending node as approved, re-executes the workflow, and persists the result

8. **Add approval gate to charity care workflow** (`src/cen/modules/charity_care_navigator.json`)
   - Inserted `counselor_approval` APPROVAL node between action nodes and `handoff_counselor`

9. **Add engine unit tests for APPROVAL** (`tests/core/test_engine.py`)
   - Stops at unapproved gate with `pending_approval:` outcome
   - Passes through approved gate and continues execution
   - Sets `{node_id}_status = "approved"` in context when approved

10. **Add API integration tests for approval flow** (`tests/api/test_sessions.py`)
    - Full lifecycle: create session, execute (stops at gate), approve, verify completion
    - 409 on approving a non-AWAITING_APPROVAL session
    - 404 on approving a nonexistent session

11. **Update existing workflow tests** (`tests/api/test_workflows.py`)
    - Updated charity care assertions to expect `pending_approval:` outcome and `counselor_approval` in executed nodes
