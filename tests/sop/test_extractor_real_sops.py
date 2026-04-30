"""End-to-end extractor tests against the two real SOPs that motivated
this feature. They live in tests/sop/fixtures/.

These are the fidelity bar: a regression here means the regex
extractor lost ground on the documents it's supposed to handle out of
the box.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cen.core.models import NodeType
from cen.sop.extractor import RegexExtractor
from cen.sop.validators import has_blocking_errors, validate_draft


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def proforma_md() -> str:
    return (FIXTURES / "proforma.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def realestate_md() -> str:
    return (FIXTURES / "realestate.md").read_text(encoding="utf-8")


def test_proforma_extracts_many_nodes(proforma_md: str):
    draft = RegexExtractor().extract(
        canonical_md=proforma_md,
        sop_id="sop_proforma",
        suggested_module_name="proforma",
    )
    assert len(draft.nodes) >= 10, "expected at least 10 nodes from the Proforma SOP"
    # The first node is the intake step.
    first = draft.nodes[0]
    assert first.id == "pf_01"
    assert first.metadata.actor and "csr" in first.metadata.actor.lower()
    assert first.metadata.source_ref is not None
    assert first.metadata.source_ref.sop_id == "sop_proforma"


def test_proforma_decision_gates_become_conditions(proforma_md: str):
    draft = RegexExtractor().extract(
        canonical_md=proforma_md,
        sop_id="sop_proforma",
        suggested_module_name="proforma",
    )
    conditions = [n for n in draft.nodes if n.type == NodeType.CONDITION]
    assert len(conditions) >= 1, "DECISION GATE blocks should produce CONDITION nodes"
    # Every CONDITION should have at least one branch wired up.
    for c in conditions:
        assert c.true_next or (c.branches and len(c.branches) >= 1)


def test_realestate_dual_track_extracts(realestate_md: str):
    draft = RegexExtractor().extract(
        canonical_md=realestate_md,
        sop_id="sop_realestate",
        suggested_module_name="realestate",
    )
    # Listing-agent (LA-##) and buyer-agent (BA-##) ids both present.
    ids = {n.id for n in draft.nodes}
    assert any(i.startswith("la_") for i in ids), "listing-agent nodes missing"
    assert any(i.startswith("ba_") for i in ids), "buyer-agent nodes missing"


def test_real_sops_have_provenance_on_every_node(proforma_md, realestate_md):
    for md, sop_id in [(proforma_md, "sop_proforma"), (realestate_md, "sop_realestate")]:
        draft = RegexExtractor().extract(
            canonical_md=md, sop_id=sop_id, suggested_module_name="m"
        )
        for n in draft.nodes:
            assert n.metadata.source_ref is not None, f"missing source_ref on {n.id}"
            assert n.metadata.source_ref.sop_id == sop_id
            assert n.metadata.source_ref.excerpt


def test_real_sops_validate_with_cycle_errors_only(proforma_md, realestate_md):
    """The Proforma and real-estate SOPs both contain explicit revision
    loops ("if NO, refine and re-submit"). The current engine rejects
    cycles, so the validator surfaces those — and ONLY those — as
    errors. Anything else (missing branches, unknown ids) is a
    regression in the extractor."""
    for md, sop_id in [(proforma_md, "sop_proforma"), (realestate_md, "sop_realestate")]:
        draft = RegexExtractor().extract(
            canonical_md=md, sop_id=sop_id, suggested_module_name="m"
        )
        issues = validate_draft(draft)
        errors = [i for i in issues if i.severity == "error"]
        non_cycle_errors = [i for i in errors if "cycle" not in i.message.lower()]
        assert not non_cycle_errors, (
            f"{sop_id} has non-cycle blocking errors: "
            f"{[(i.node_id, i.message) for i in non_cycle_errors]}"
        )
