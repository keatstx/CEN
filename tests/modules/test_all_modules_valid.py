"""Parameterized test validating all 5 AOP modules load and execute."""

from __future__ import annotations

from pathlib import Path

import pytest

from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import WorkflowInput

MODULES_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "cen" / "modules"

# Universal patient identity fields — required by every module's
# entry intake node (intake_start / case_create) per the v1 input
# schema authoring pass.
_PATIENT = {
    "patient_name": "Test Patient",
    "patient_dob": "1980-01-01",
}

MODULE_CONTEXTS = {
    "charity_care_navigator": {**_PATIENT, "income_fpl_percent": 150},
    "debt_cancellation_engine": {
        **_PATIENT,
        "bill_summary": "test bill",
        "violations_count": 2,
        # ingest_bill input_schema requires these
        "bill_total_amount": 1234.56,
        "provider_name": "Test Hospital",
    },
    "insurance_appeal_assistant": {
        **_PATIENT,
        "denial_reason": "claim denied",
        "denial_type": "medical_necessity",
        # denial_intake input_schema requires claim_number too
        "claim_number": "TEST-12345",
    },
    "benefits_enrollment_navigator": {
        **_PATIENT,
        "income_fpl_percent": 100,
        "has_children_under_19": True,
        # collect_household input_schema requires these
        "household_size": 4,
        "annual_household_income": 35000,
    },
    "community_resource_router": {
        **_PATIENT,
        # sdoh_screener input_schema requires zip_code
        "needs_housing": True,
        "needs_food": False,
        "needs_transport": True,
        "zip_code": "12345",
    },
    "master_case_orchestrator": {
        **_PATIENT,
        # triage_intake input_schema requires primary_concern
        "primary_concern": "medical_debt",
    },
}


def _get_module_files():
    return sorted(MODULES_DIR.glob("*.json"))


@pytest.mark.parametrize(
    "module_file",
    _get_module_files(),
    ids=lambda p: p.stem,
)
class TestAllModules:
    def test_loads_without_error(self, module_file: Path):
        aop = load_aop_from_file(module_file)
        engine = AsyncWorkflowEngine()
        engine.load_aop(aop)
        assert len(engine.nodes) > 0

    async def test_executes_to_completion(self, module_file: Path):
        aop = load_aop_from_file(module_file)
        engine = AsyncWorkflowEngine()
        engine.load_aop(aop)
        context = MODULE_CONTEXTS.get(aop.module_name, {})
        result = await engine.execute(
            WorkflowInput(module_name=aop.module_name, context=context)
        )
        assert len(result.executed_nodes) > 0
        assert result.final_outcome != ""
