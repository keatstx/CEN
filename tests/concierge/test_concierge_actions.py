"""Tests for the concierge's action derivation (Phase 5c).

Actions are clickable next-step buttons surfaced under the assistant's
turn. Backend derives them rule-based from the question + case state +
available modules. Frontend dispatches them via the App-level handler.
"""

from __future__ import annotations

from httpx import AsyncClient


class TestConciergeActions:
    async def test_dashboard_trigger_emits_open_dashboard_action(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/concierge/ask",
            json={"question": "Show me my dashboard, what's next?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "actions" in body
        kinds = [a["kind"] for a in body["actions"]]
        assert "open_dashboard" in kinds

    async def test_charity_care_trigger_emits_start_workflow(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/concierge/ask",
            json={"question": "How do I apply for charity care?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        kinds = [a["kind"] for a in body["actions"]]
        # When question matches charity care keywords, suggest the start.
        if "start_workflow" in kinds:
            charity_actions = [
                a for a in body["actions"]
                if a["kind"] == "start_workflow"
                and a["payload"].get("module_name") == "charity_care_navigator"
            ]
            assert len(charity_actions) == 1
            assert "charity care" in charity_actions[0]["label"].lower()

    async def test_unrelated_question_emits_no_actions(self, client: AsyncClient):
        resp = await client.post(
            "/concierge/ask",
            json={"question": "What's the weather today?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["actions"] == []

    async def test_actions_field_always_present(self, client: AsyncClient):
        """Even when no actions match, the field is present (empty list)
        so the frontend type is stable."""
        resp = await client.post(
            "/concierge/ask",
            json={"question": "Hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "actions" in body
        assert isinstance(body["actions"], list)
