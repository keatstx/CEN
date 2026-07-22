"""GENERATE node runtime — document production for ACTION nodes whose
``metadata.action_kind == "generate"``.

Split out of ``engine_runtime`` per CLAUDE.md §4.9 (that file is already
at the size bar). ``run_action_node`` delegates here when it hits a
generate node on the first-time (cache-miss) path; the cache-replay and
input-schema-pause paths are handled by ``run_action_node`` itself, so
this module only implements first-time generation.

Design constraints honored:
- Non-Negotiable #1: the assembled prompt is PII-scrubbed before it
  reaches the LLM.
- Non-Negotiable #3: output is written to ``state.node_outputs`` so a
  resumed case replays the cached document instead of regenerating.
- Non-Negotiable #9: every generated document carries provenance
  ``{model, prompt_version, timestamp, output_kind}``.
- §3 Layering: the engine stays pure — the document lands in context;
  persisting it as a downloadable artifact is a route-layer concern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from cen.core.engine_runtime import ExecutionState, StepResult
from cen.core.models import AOPNode, InputField

if TYPE_CHECKING:
    from cen.core.engine import AsyncWorkflowEngine


def _render_prompt(template: str, keys: list[str], context: dict[str, Any]) -> str:
    """Fill ``{key}`` placeholders from context by targeted replacement.

    Deliberately not ``str.format`` — generate templates often contain
    literal braces (JSON examples, letter formatting) that would break
    format(). Only the declared input_fields are substituted.
    """
    rendered = template
    for key in keys:
        rendered = rendered.replace("{" + key + "}", str(context.get(key, "")))
    return rendered


async def run_generate_node(
    engine: "AsyncWorkflowEngine",
    node: AOPNode,
    state: ExecutionState,
    session_id: str | None,
) -> StepResult:
    """First-time execution of a document-generation ACTION node."""
    spec = node.metadata.generate
    assert spec is not None  # guarded by the caller

    # Pause if any template input the document needs is missing. These
    # may be collected via input_schema or produced upstream; either
    # way, don't generate a document full of blanks.
    missing_keys = [k for k in spec.input_fields if not state.context.get(k)]
    if missing_keys:
        fields = [
            InputField(key=k, label=k.replace("_", " ").title(), required=True)
            for k in missing_keys
        ]
        state.pending_input_node = node.id
        state.pending_input_fields = fields
        state.outcome = f"pending_input:{node.metadata.label or node.id}"
        await engine._emit_node_event(
            session_id, node.id, "ACTION", "pending_input", state.context
        )
        return StepResult.BREAK

    state.executed.append(node.id)

    # Assemble → SCRUB → generate (Non-Negotiable #1).
    rendered = _render_prompt(spec.prompt, spec.input_fields, state.context)
    if engine._scrubber is not None:
        rendered = engine._scrubber.scrub(rendered)

    if engine._llm is not None:
        document = await engine._llm.generate(rendered, max_tokens=800)
        model_name = engine._llm.backend_name
    else:
        # Dev/test without an LLM: produce a deterministic placeholder so
        # the workflow still advances. Never reached in production.
        document = f"[{spec.output_kind} could not be generated: no AI backend configured]"
        model_name = "none"

    provenance = {
        "model": model_name,
        "prompt_version": spec.prompt_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_kind": spec.output_kind,
    }

    output: dict[str, Any] = {
        f"{node.id}_document": document,
        f"{node.id}_provenance": provenance,
        f"{node.id}_status": "done",
    }
    if node.metadata.auto_set:
        for k, v in node.metadata.auto_set.items():
            output[k] = v

    for k, v in output.items():
        state.context[k] = v
    state.node_outputs[node.id] = output

    await engine._emit_node_event(
        session_id, node.id, "ACTION", "generated", state.context
    )
    return StepResult.CONTINUE
