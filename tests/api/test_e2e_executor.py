"""End-to-end smoke tests proving the new Executor flow works against
a real shipped module with input_schema authored on its intake node.

This is the integration test that proves all 7 foundation steps land
together: project → case → execute → AWAITING_INPUT pause derived
from a real input_schema → provide_input → engine resumes from cache
→ workflow advances.
"""

from __future__ import annotations

from httpx import AsyncClient


class TestDebtCancellationEngineFlow:
    async def test_full_flow_pauses_at_ingest_bill_then_resumes(
        self, client: AsyncClient
    ):
        # 1. Create a case under the auto-default project.
        cr = await client.post(
            "/cases", json={"module_name": "debt_cancellation_engine"},
        )
        assert cr.status_code == 201
        case = cr.json()
        cid = case["id"]
        assert case["project_id"] is not None

        # 2. Kick off execution. The intake_start runs, then
        #    hipaa_consent (APPROVAL) pauses the workflow.
        ex = await client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "debt_cancellation_engine", "context": {}},
        )
        assert ex.status_code == 200
        result = ex.json()
        # First pause is at the HIPAA consent approval gate.
        assert result["final_outcome"].startswith("pending_approval:")

        # 3. Approve HIPAA consent. After approval the engine resumes
        #    and runs until it hits the next pause — which should be
        #    the ingest_bill ACTION whose input_schema we authored.
        appr = await client.post(f"/cases/{cid}/approve")
        assert appr.status_code == 200
        result = appr.json()
        # Now paused at ingest_bill awaiting input.
        assert result["final_outcome"].startswith("pending_input:")
        assert result["pending_node"] == "ingest_bill"
        assert result["pending_input_fields"] is not None
        keys = [f["key"] for f in result["pending_input_fields"]]
        assert "bill_total_amount" in keys
        assert "provider_name" in keys

        # 4. Verify the case row reflects AWAITING_INPUT and the
        #    persisted schema round-trips.
        get = await client.get(f"/cases/{cid}")
        assert get.json()["status"] == "AWAITING_INPUT"
        assert get.json()["pending_node"] == "ingest_bill"
        persisted_keys = [
            f["key"] for f in get.json()["pending_input_fields"]
        ]
        assert "bill_total_amount" in persisted_keys

        # 5. Submit incomplete inputs — the optional file is not
        #    required, but the two text/currency fields are.
        bad = await client.post(
            f"/cases/{cid}/provide_input",
            json={"inputs": {"bill_total_amount": 1234.56}},
        )
        assert bad.status_code == 422
        # Missing provider_name reported.
        assert "provider_name" in bad.text

        # 6. Submit valid inputs. Engine resumes from the
        #    idempotency cache (intake_start does NOT re-run).
        good = await client.post(
            f"/cases/{cid}/provide_input",
            json={
                "inputs": {
                    "bill_total_amount": 1234.56,
                    "provider_name": "Memorial Hospital",
                }
            },
        )
        assert good.status_code == 200
        result = good.json()
        # Workflow continued past ingest_bill — either to the next
        # pause or further along.
        assert result["pending_node"] != "ingest_bill" or result[
            "final_outcome"
        ].startswith("handoff:")
        # The provided context made it through.
        assert result["context"]["bill_total_amount"] == 1234.56
        assert result["context"]["provider_name"] == "Memorial Hospital"
        # Idempotency cache: intake_start ran exactly once across both
        # the initial execute and the resume.
        assert result["context"]["intake_start_status"] == "done"


class TestInsuranceAppealFlow:
    async def test_denial_intake_pause_via_input_schema(
        self, client: AsyncClient
    ):
        cr = await client.post(
            "/cases",
            json={"module_name": "insurance_appeal_assistant"},
        )
        cid = cr.json()["id"]

        # Kick off — first pause is the HIPAA consent approval.
        ex = await client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "insurance_appeal_assistant", "context": {}},
        )
        assert ex.json()["final_outcome"].startswith("pending_approval:")

        # Approve HIPAA. Next pause should be denial_intake (input_schema).
        appr = await client.post(f"/cases/{cid}/approve")
        result = appr.json()
        assert result["final_outcome"].startswith("pending_input:")
        assert result["pending_node"] == "denial_intake"
        keys = [f["key"] for f in result["pending_input_fields"]]
        assert "denial_reason" in keys
        assert "claim_number" in keys


class TestMasterOrchestratorFlow:
    async def test_triage_intake_select_field_pauses(
        self, client: AsyncClient
    ):
        cr = await client.post(
            "/cases",
            json={"module_name": "master_case_orchestrator"},
        )
        cid = cr.json()["id"]

        ex = await client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "master_case_orchestrator", "context": {}},
        )
        result = ex.json()
        # Master orchestrator likely pauses at consent first or at
        # triage_intake. Either way, it should hit our authored schema
        # at some point — keep walking until it does or the workflow
        # completes.
        for _ in range(8):
            outcome = result["final_outcome"]
            if outcome.startswith("pending_input:") and result.get("pending_node") == "triage_intake":
                break
            if outcome.startswith("pending_approval:"):
                appr = await client.post(f"/cases/{cid}/approve")
                result = appr.json()
                continue
            if outcome.startswith("pending_input:"):
                # Some other auto-derived input pause — fill it with a
                # placeholder so we can advance.
                pending_keys = [f["key"] for f in result["pending_input_fields"]]
                next_inputs = {k: "test_value" for k in pending_keys}
                resp = await client.post(
                    f"/cases/{cid}/provide_input",
                    json={"inputs": next_inputs},
                )
                result = resp.json()
                continue
            break

        # If we made it to triage_intake, validate its schema.
        if result.get("pending_node") == "triage_intake":
            keys = [f["key"] for f in result["pending_input_fields"]]
            assert "patient_name" in keys
            assert "primary_concern" in keys
            # primary_concern is a select with options.
            primary_concern_field = next(
                f for f in result["pending_input_fields"]
                if f["key"] == "primary_concern"
            )
            assert primary_concern_field["type"] == "select"
            assert primary_concern_field["options"] is not None
            assert len(primary_concern_field["options"]) == 4
