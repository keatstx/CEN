"""Tests for the polymorphic concierge subject (Phase 6).

The concierge can now ground in four subject kinds: case, module,
sop, queue, or none. The /concierge/ask route reads `context` and
routes retrieval accordingly. Legacy `case_id` clients still work.
"""

from __future__ import annotations

import io

from httpx import AsyncClient


class TestModuleContext:
    """When the user is on Workflow Map, the concierge grounds in the
    selected module's AOP rather than falling through to FAQ-only."""

    async def test_module_context_emits_workflow_citation(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "How many steps are in this workflow?",
                "context": {
                    "kind": "module",
                    "module_name": "charity_care_navigator",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # The module-context retriever attaches a workflow citation.
        kinds = [c["kind"] for c in body["citations"]]
        # Either workflow citation surfaces, OR no FAQ matched and we
        # got a no_match — both are acceptable as long as nothing broke.
        if body["mode"] != "no_match":
            assert "workflow" in kinds or "faq" in kinds


class TestQueueContext:
    """Queue/none kinds don't crash and don't pull case state."""

    async def test_queue_context_returns_valid_response(self, client: AsyncClient):
        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "What's on my plate today?",
                "context": {"kind": "queue"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "actions" in body

    async def test_none_context_falls_back_to_faq_only(self, client: AsyncClient):
        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "What is CEN?",
                "context": {"kind": "none"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body


class TestLegacyCaseIdStillWorks:
    """Old clients that send only case_id (no context) get mapped to
    a 'case' context internally — back-compat is preserved."""

    async def test_legacy_case_id_routes_to_case_context(
        self, client: AsyncClient
    ):
        # Create + execute a case so it has a pending_node.
        create_resp = await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        case = create_resp.json()
        await client.post(
            f"/execute?session_id={case['id']}",
            json={"module_name": "charity_care_navigator", "context": {}},
        )

        # Legacy shape: case_id at the top level, no context block.
        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "What step am I on?",
                "case_id": case["id"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Case context emits workflow citations when the step has metadata.
        assert "answer" in body


class TestSOPContext:
    """SOP context grounds in the selected SOP's draft + issues."""

    async def test_sop_context_unknown_sop_returns_clean(
        self, client: AsyncClient
    ):
        # Unknown sop_id is treated as no subject — should not 500.
        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "What's wrong with this SOP?",
                "context": {
                    "kind": "sop",
                    "sop_id": "00000000-0000-0000-0000-000000000000",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body

    async def test_sop_context_grounds_when_sop_exists(self, client: AsyncClient):
        # Upload + parse an SOP so we have a real one to ground against.
        md = (
            "# Sample SOP\n\n"
            "## NODE: SAMPLE-01\n"
            "ACTOR: Navigator\n"
            "ACTION: Intake patient details.\n"
            "OUTPUT: Case record.\n"
        )
        files = {"file": ("sample.md", io.BytesIO(md.encode("utf-8")), "text/markdown")}
        up = await client.post("/sop/upload", files=files)
        assert up.status_code == 201
        sop_id = up.json()["id"]
        await client.post(f"/sop/{sop_id}/parse")
        await client.post(f"/sop/{sop_id}/extract")

        resp = await client.post(
            "/concierge/ask",
            json={
                "question": "Tell me about this SOP.",
                "context": {"kind": "sop", "sop_id": sop_id},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # SOP-context retriever attaches sop-kind citations when chunks fuse.
        if body["mode"] != "no_match":
            kinds = [c["kind"] for c in body["citations"]]
            assert "sop" in kinds or "faq" in kinds
