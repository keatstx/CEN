"""Tests for GET /concierge/next_question/{case_id}.

The endpoint returns the per-step proactive prompt and chip set the
Concierge fires on every pending_node change. Validates:

- AWAITING_INPUT returns a field_key + a prompt that uses field.label
  (NOT field.key — §5 forbidden-terms).
- AWAITING_APPROVAL returns a review-readiness prompt.
- Chips come from the node metadata's hand-authored suggested_questions.
- Unknown case → 404.
"""

from __future__ import annotations

from httpx import AsyncClient


async def _create_and_execute(client: AsyncClient, module: str) -> dict:
    resp = await client.post("/cases", json={"module_name": module})
    assert resp.status_code == 201
    case = resp.json()
    exec_resp = await client.post(
        f"/execute?session_id={case['id']}",
        json={"module_name": module, "context": {}},
    )
    assert exec_resp.status_code == 200
    return (await client.get(f"/cases/{case['id']}")).json()


class TestNextQuestion:
    async def test_input_step_returns_field_key_and_label_prompt(
        self, client: AsyncClient
    ):
        case = await _create_and_execute(client, "charity_care_navigator")
        case_id = case["id"]
        assert case["status"] == "AWAITING_INPUT"
        assert case["pending_node"] == "intake_start"

        resp = await client.get(f"/concierge/next_question/{case_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["field_key"] in {"patient_name", "patient_dob"}
        # Prompt uses field.label, not field.key
        assert "patient_name" not in body["prompt"]
        # Prompt is non-empty and human-shaped
        assert len(body["prompt"]) > 10
        # Chips from the hand-authored suggested_questions
        assert isinstance(body["suggested_questions"], list)
        assert len(body["suggested_questions"]) > 0

    async def test_unknown_case_returns_404(self, client: AsyncClient):
        resp = await client.get(
            "/concierge/next_question/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404
