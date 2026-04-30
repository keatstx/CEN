"""Promoter tests — versioning, error gating, engine registration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
)
from cen.sop.promoter import PromotionError, promote_draft


class _StubLLM:
    backend = "stub"

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        return "stub response"


class _StubEventBus:
    async def emit(self, event: object) -> None:  # noqa: D401
        return None


def _draft(module_name: str, nodes_count: int = 2) -> AOPDefinition:
    nodes = [
        AOPNode(id=f"n{i}", type=NodeType.ACTION, metadata=NodeMetadata(label=f"n{i}"))
        for i in range(nodes_count)
    ]
    edges = [AOPEdge(source=f"n{i}", target=f"n{i+1}") for i in range(nodes_count - 1)]
    return AOPDefinition(
        module_name=module_name,
        version="0.0",
        description="",
        source_doc="sop_test",
        nodes=nodes,
        edges=edges,
    )


def test_promote_writes_file_and_registers_engine(tmp_path: Path):
    engines: dict = {}
    promoted = promote_draft(
        draft=_draft("test_module"),
        modules_dir=tmp_path,
        engines=engines,
        llm=_StubLLM(),
        event_bus=_StubEventBus(),
        llm_semaphore=asyncio.Semaphore(1),
    )
    assert promoted.version == "1.0"
    assert "test_module" in engines
    out = tmp_path / "test_module_v1.0.json"
    assert out.exists()
    saved = json.loads(out.read_text())
    assert saved["module_name"] == "test_module"
    assert saved["version"] == "1.0"


def test_promote_bumps_version_on_repeat(tmp_path: Path):
    engines: dict = {}
    p1 = promote_draft(
        draft=_draft("m"),
        modules_dir=tmp_path,
        engines=engines,
        llm=_StubLLM(),
        event_bus=_StubEventBus(),
        llm_semaphore=asyncio.Semaphore(1),
    )
    p2 = promote_draft(
        draft=_draft("m"),
        modules_dir=tmp_path,
        engines=engines,
        llm=_StubLLM(),
        event_bus=_StubEventBus(),
        llm_semaphore=asyncio.Semaphore(1),
    )
    assert p1.version == "1.0"
    assert p2.version == "1.1"
    assert (tmp_path / "m_v1.0.json").exists()
    assert (tmp_path / "m_v1.1.json").exists()


def test_promote_refuses_drafts_with_errors(tmp_path: Path):
    bad = AOPDefinition(
        module_name="bad",
        nodes=[
            AOPNode(
                id="cond",
                type=NodeType.CONDITION,
                metadata=NodeMetadata(label="c"),
                # no true_next / false_next -> error
            )
        ],
        edges=[],
    )
    with pytest.raises(PromotionError):
        promote_draft(
            draft=bad,
            modules_dir=tmp_path,
            engines={},
            llm=_StubLLM(),
            event_bus=_StubEventBus(),
            llm_semaphore=asyncio.Semaphore(1),
        )


def test_promote_renames_module_when_requested(tmp_path: Path):
    engines: dict = {}
    promoted = promote_draft(
        draft=_draft("auto_name"),
        modules_dir=tmp_path,
        engines=engines,
        llm=_StubLLM(),
        event_bus=_StubEventBus(),
        llm_semaphore=asyncio.Semaphore(1),
        requested_name="custom_name",
    )
    assert promoted.module_name == "custom_name"
    assert "custom_name" in engines
    assert (tmp_path / "custom_name_v1.0.json").exists()
