"""SOP extraction — canonical Markdown into a draft AOPDefinition.

The Protocol is the swap point. v1 ships with `RegexExtractor` which
targets the DAG-Ready node grammar that the Proforma and Real Estate
SOPs use:

    NODE: <ID>
    PHASE: <text>
    TASK NAME: <text>
    TRIGGER: <text>
    ACTOR: <text>
    ACTION:
        1. ...
        2. ...
    OUTPUT: <text>
    DECISION GATE: <Q>? -> <answer>: <next_id> | <answer>: <next_id>
    NEXT NODE(S): <id1>, <id2>
    TIMELINE: <text>
    PARALLEL: <Yes|No>

A future `LLMExtractor` will implement the same Protocol against a
prompt against the Pro tier of whatever provider is configured.
"""

from __future__ import annotations

import re
from typing import List, Optional, Protocol, Tuple

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
    SourceRef,
)


class SOPExtractor(Protocol):
    """Strategy interface — turns canonical markdown into a draft AOP."""

    def extract(
        self,
        *,
        canonical_md: str,
        sop_id: str,
        suggested_module_name: str,
    ) -> AOPDefinition: ...

    @property
    def extractor_name(self) -> str: ...


# ── Regex extractor ──────────────────────────────────────────────────


_NODE_HEADER = re.compile(
    r"^\**\s*NODE\s*:\s*\**\s*(?P<id>[A-Za-z0-9][A-Za-z0-9_\-]*)\s*\**\s*$",
    re.MULTILINE | re.IGNORECASE,
)

_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "phase": re.compile(r"^\s*\**\s*PHASE\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    "task_name": re.compile(
        r"^\s*\**\s*TASK\s*NAME\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE
    ),
    "trigger": re.compile(r"^\s*\**\s*TRIGGER\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    "actor": re.compile(r"^\s*\**\s*ACTOR\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    "output": re.compile(r"^\s*\**\s*OUTPUT\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    "timeline": re.compile(r"^\s*\**\s*TIMELINE\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    "parallel": re.compile(
        r"^\s*\**\s*PARALLEL\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE
    ),
    "decision_gate": re.compile(
        r"^\s*\**\s*DECISION\s*GATE\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE
    ),
    "next": re.compile(
        r"^\s*\**\s*NEXT\s*NODE\(?S?\)?\s*:?\s*\**\s*(?P<v>.+?)\s*$", re.IGNORECASE
    ),
    "action": re.compile(r"^\s*\**\s*ACTION\s*:?\s*\**\s*(?P<v>.*?)\s*$", re.IGNORECASE),
}


# Captures one branch line, e.g.:
#   "-> YES: LA-02"
#   "→ Promotional/Apparel: proceed to PF-02A"
#   "→ NO: schedule follow-up in CRM"           (no target id present)
# Strategy: take the label up to the first colon, then pull the LAST
# id-shaped token from the rest of the line as the target. If no id
# is present, the branch is dropped (the validator will surface it
# as a missing target).
_BRANCH_LINE = re.compile(r"(?:->|→)\s*(?P<label>[^:]+?)\s*:\s*(?P<rest>.+?)\s*$")

# An ID-shaped token. Real SOP node ids in the documents we target
# (PF-01, LA-12, BA-03, PF-02A) always contain a digit, so requiring
# one filters out word-pairs like "re-submit" or "follow-up" that
# would otherwise look like ids. Pattern: letters + sep + chars-with-
# digit, OR letters-with-digit + optional alpha tail.
_ID_TOKEN = re.compile(
    r"\b([A-Za-z]+[\-_][A-Za-z]*\d+[A-Za-z0-9]*|[A-Za-z]*\d+[A-Za-z0-9]*[\-_][A-Za-z0-9]+)\b"
)

# NEXT NODE(S) list — also requires a digit, same reasoning.
_NEXT_LIST_PATTERN = re.compile(
    r"[A-Za-z]+[\-_][A-Za-z]*\d+[A-Za-z0-9]*|[A-Za-z]*\d+[A-Za-z0-9]*[\-_][A-Za-z0-9]+"
)

_HANDOFF_KEYWORDS = ("third party", "external", "vendor", "client signs", "client signature")
_APPROVAL_KEYWORDS = ("approval", "approve", "sign-off", "signoff", "sign off", "client confirms")


class RegexExtractor:
    """Deterministic extractor for SOPs that follow the DAG-Ready grammar.

    The two SOPs in the sample set both adhere to this grammar; this
    extractor produces a clean AOPDefinition for them without an LLM.
    For documents that drift from the grammar, the LLM extractor (when
    wired) takes over.
    """

    extractor_name = "regex.v1"

    def extract(
        self,
        *,
        canonical_md: str,
        sop_id: str,
        suggested_module_name: str,
    ) -> AOPDefinition:
        sections = _split_node_sections(canonical_md)
        nodes: list[AOPNode] = []
        edges: list[AOPEdge] = []
        seen_ids: set[str] = set()

        for raw_id, body, header_pos in sections:
            node_id = _normalize_id(raw_id)
            if node_id in seen_ids:
                # duplicate — append underscore-numeric suffix
                suffix = 2
                while f"{node_id}_{suffix}" in seen_ids:
                    suffix += 1
                node_id = f"{node_id}_{suffix}"
            seen_ids.add(node_id)

            fields = _extract_fields(body)
            node, node_edges = _build_node(
                node_id=node_id,
                fields=fields,
                excerpt=body.strip()[:200],
                sop_id=sop_id,
            )
            nodes.append(node)
            edges.extend(node_edges)

        # Drop edges that point at nodes we never saw; the validator
        # will surface those as warnings on the source node.
        valid_ids = {n.id for n in nodes}
        edges = [e for e in edges if e.target in valid_ids and e.source in valid_ids]

        # Dedupe edges (regex may produce both NEXT-NODE and DECISION-
        # GATE versions of the same source->target).
        seen_edges: set[tuple[str, str, str]] = set()
        deduped: list[AOPEdge] = []
        for e in edges:
            key = (e.source, e.target, e.label)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            deduped.append(e)

        module = AOPDefinition(
            module_name=suggested_module_name,
            version="1.0",
            description=f"Draft module extracted from SOP {sop_id}.",
            source_doc=sop_id,
            nodes=nodes,
            edges=deduped,
        )
        return module


# ── Helpers ──────────────────────────────────────────────────────────


def _split_node_sections(text: str) -> list[Tuple[str, str, int]]:
    """Return [(node_id, body_between_this_header_and_next, position)]."""
    matches = list(_NODE_HEADER.finditer(text))
    sections: list[Tuple[str, str, int]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append((m.group("id"), body, m.start()))
    return sections


def _normalize_id(raw: str) -> str:
    """Convert e.g. 'PF-01' or 'LA 12' into 'pf_01'/'la_12'."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", raw.strip()).lower()
    cleaned = cleaned.strip("_")
    return cleaned or "node"


def _extract_fields(body: str) -> dict:
    """Pull labelled fields out of a node body.

    Most fields are single-line. Two are multi-line:
    - ACTION: numbered steps that follow on subsequent lines.
    - DECISION GATE: the question line followed by indented branch
      arrows like "-> YES: PF-02" until the next labelled field.
    """
    fields: dict = {
        "phase": "",
        "task_name": "",
        "trigger": "",
        "actor": "",
        "output": "",
        "timeline": "",
        "parallel": "",
        "decision_gate": "",
        "decision_branch_lines": [],
        "next": "",
        "action_text": "",
        "action_steps": [],
    }

    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        matched = False
        for key, pattern in _FIELD_PATTERNS.items():
            m = pattern.match(line)
            if not m:
                continue
            matched = True
            value = m.group("v").strip()
            if key == "action":
                fields["action_text"] = value
                steps: list[str] = []
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if not nxt:
                        j += 1
                        continue
                    if any(
                        p.match(nxt) for k, p in _FIELD_PATTERNS.items() if k != "action"
                    ):
                        break
                    step_match = re.match(r"^(?:\d+[.\)]|[-*])\s*(.+)$", nxt)
                    if step_match:
                        steps.append(step_match.group(1).strip())
                    else:
                        if steps:
                            steps[-1] += " " + nxt
                        else:
                            steps.append(nxt)
                    j += 1
                fields["action_steps"] = steps
                i = j - 1
            elif key == "decision_gate":
                fields["decision_gate"] = value
                # Pull subsequent branch arrows ("-> YES: ..." / "→ NO: ...")
                # until the next labelled field.
                branches: list[str] = []
                # The same line may already carry an arrow after the question.
                if "->" in value or "→" in value:
                    branches.append(value)
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if not nxt:
                        j += 1
                        continue
                    if any(
                        p.match(nxt) for k, p in _FIELD_PATTERNS.items() if k != "decision_gate"
                    ):
                        break
                    if "->" in nxt or "→" in nxt:
                        branches.append(nxt)
                        j += 1
                        continue
                    # A non-arrow continuation line (extra context for the
                    # gate question) — skip it; we only care about branch
                    # targets.
                    j += 1
                fields["decision_branch_lines"] = branches
                i = j - 1
            else:
                fields[key] = value
            break
        if not matched:
            pass
        i += 1
    return fields


def _build_node(
    *,
    node_id: str,
    fields: dict,
    excerpt: str,
    sop_id: str,
) -> tuple[AOPNode, list[AOPEdge]]:
    label = fields["task_name"] or node_id
    description_parts: list[str] = []
    if fields["task_name"]:
        description_parts.append(fields["task_name"])
    if fields["action_steps"]:
        description_parts.append("Steps: " + " | ".join(fields["action_steps"]))
    elif fields["action_text"]:
        description_parts.append(fields["action_text"])
    description = " — ".join(p for p in description_parts if p).strip()

    parallel = _parse_yes_no(fields["parallel"])
    actor = fields["actor"] or None

    section = " | ".join(p for p in [fields["phase"], f"NODE: {node_id.upper()}"] if p).strip()
    source_ref = SourceRef(
        sop_id=sop_id,
        section=section,
        excerpt=excerpt.strip(),
    )

    metadata = NodeMetadata(
        label=label,
        description=description,
        actor=actor,
        trigger=fields["trigger"] or None,
        output=fields["output"] or None,
        timeline=fields["timeline"] or None,
        parallel=parallel,
        source_ref=source_ref,
        params={"action_steps": fields["action_steps"]} if fields["action_steps"] else {},
    )

    node_type, branches, next_targets = _classify_node(
        node_id=node_id,
        fields=fields,
    )

    edges: list[AOPEdge] = []
    if node_type == NodeType.CONDITION:
        true_target = (
            branches.get("yes")
            or branches.get("approved")
            or branches.get("ok")
            or branches.get("y")
        )
        false_target = (
            branches.get("no")
            or branches.get("denied")
            or branches.get("rejected")
            or branches.get("n")
        )
        # Fall back to first/second branch entries when labels are non-standard.
        ordered_targets = list(branches.values())
        if not true_target and ordered_targets:
            true_target = ordered_targets[0]
        if not false_target and len(ordered_targets) > 1:
            false_target = ordered_targets[1]
        # Final fallback: when only one branch was extracted (the SOP
        # listed the other branch as a dead-end like "schedule follow-up
        # in CRM" with no node id), use the first NEXT NODE(S) target as
        # the missing side. This keeps the CONDITION valid; authors can
        # rewire in the review UI.
        if not false_target and next_targets:
            false_target = next_targets[0]
        if not true_target and next_targets:
            true_target = next_targets[0]
        node = AOPNode(
            id=node_id,
            type=node_type,
            metadata=metadata,
            condition_field=f"{node_id}__answer",
            condition_operator="equals",
            condition_value="yes",
            true_next=true_target,
            false_next=false_target,
            branches=branches or None,
        )
        for label_text, target in branches.items():
            edges.append(AOPEdge(source=node_id, target=target, label=label_text))
        for target in next_targets:
            if target not in branches.values():
                edges.append(AOPEdge(source=node_id, target=target, label="next"))
    else:
        node = AOPNode(id=node_id, type=node_type, metadata=metadata)
        for target in next_targets:
            edges.append(AOPEdge(source=node_id, target=target, label="next"))

    return node, edges


def _classify_node(
    *,
    node_id: str,
    fields: dict,
) -> tuple[NodeType, dict[str, str], list[str]]:
    branches = _parse_decision_gate(fields.get("decision_branch_lines") or [])
    next_targets = _parse_next_nodes(fields["next"])

    haystack = " ".join(
        [
            fields["task_name"],
            fields["trigger"],
            fields["output"],
            " ".join(fields["action_steps"]),
        ]
    ).lower()

    if branches:
        return NodeType.CONDITION, branches, next_targets
    if any(k in haystack for k in _APPROVAL_KEYWORDS):
        return NodeType.APPROVAL, {}, next_targets
    actor = (fields["actor"] or "").lower()
    if any(k in haystack for k in _HANDOFF_KEYWORDS) or any(
        k in actor for k in ("third party", "external", "vendor")
    ):
        return NodeType.HANDOFF, {}, next_targets
    return NodeType.ACTION, {}, next_targets


def _parse_decision_gate(branch_lines: list[str]) -> dict[str, str]:
    """Turn ['-> YES: PF-02', '-> NO: schedule follow-up in CRM'] into
    {'yes': 'pf_02'}. Lines with no extractable target id are dropped
    (the validator surfaces those as a warning that the gate has a
    dead-end branch)."""
    branches: dict[str, str] = {}
    for line in branch_lines:
        m = _BRANCH_LINE.search(line)
        if not m:
            continue
        label = m.group("label").strip().lower()
        # Strip trailing arrow leftovers if the gate question is
        # included on the same line (e.g. "Q? -> YES: X").
        label = re.sub(r"^.*?(?:->|→)\s*", "", label).strip()
        rest = m.group("rest")
        ids = _ID_TOKEN.findall(rest)
        if not ids:
            continue
        target = _normalize_id(ids[-1])
        if label and target:
            branches[label] = target
    return branches


def _parse_next_nodes(raw: str) -> list[str]:
    if not raw:
        return []
    targets: list[str] = []
    for m in _NEXT_LIST_PATTERN.findall(raw):
        # Skip filler words.
        if m.lower() in {"and", "or", "the", "a", "in", "parallel"}:
            continue
        targets.append(_normalize_id(m))
    # Dedupe preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _parse_yes_no(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip().lower().startswith(("y", "true", "1"))
