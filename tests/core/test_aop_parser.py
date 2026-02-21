"""Tests for AOP parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cen.core.aop_parser import load_aop_from_file, parse_aop_json


def test_parse_aop_json():
    raw = {
        "module_name": "test",
        "nodes": [{"id": "a", "type": "ACTION"}],
        "edges": [],
    }
    aop = parse_aop_json(raw)
    assert aop.module_name == "test"
    assert len(aop.nodes) == 1


def test_load_aop_from_file():
    raw = {
        "module_name": "file_test",
        "nodes": [{"id": "x", "type": "HANDOFF"}],
        "edges": [],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(raw, f)
        f.flush()
        aop = load_aop_from_file(Path(f.name))
    assert aop.module_name == "file_test"
