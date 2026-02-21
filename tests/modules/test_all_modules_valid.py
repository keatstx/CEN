"""Parameterized test validating all 5 AOP modules load and execute."""

from __future__ import annotations

from pathlib import Path

import pytest

from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import WorkflowInput

MODULES_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "cen" / "modules"

MODULE_CONTEXTS = {
    "charity_care_navigator": {"income_fpl_percent": 150},
    "debt_cancellation_engine": {"bill_summary": "test bill", "violations_count": 2},
    "insurance_appeal_assistant": {
        "denial_reason": "claim denied",
        "denial_type": "medical_necessity",
    },
    "benefits_enrollment_navigator": {
        "income_fpl_percent": 100,
        "has_children_under_19": True,
    },
    "community_resource_router": {
        "needs_housing": True,
        "needs_food": False,
        "needs_transport": True,
        "zip_code": "12345",
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
