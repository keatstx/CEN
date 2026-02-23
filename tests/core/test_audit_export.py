"""Tests for audit export functions."""

from __future__ import annotations

import csv
import io
import json

from cen.core.audit_export import export_csv, export_json
from cen.core.models import AuditEntry


def _sample_entries() -> list[AuditEntry]:
    return [
        AuditEntry(
            id=1,
            session_id="s1",
            module="mod",
            node_id="n1",
            node_type="ACTION",
            outcome="done",
            context={"key": "value"},
            timestamp="2026-01-01T00:00:00Z",
            record_hash="abc123",
        ),
        AuditEntry(
            id=2,
            session_id="s1",
            module="mod",
            node_id="n2",
            node_type="CONDITION",
            outcome="passed",
            context={},
            timestamp="2026-01-01T00:00:01Z",
            record_hash="def456",
        ),
    ]


class TestExportJson:
    def test_returns_valid_json(self):
        result = export_json(_sample_entries())
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_contains_all_fields(self):
        result = export_json(_sample_entries())
        parsed = json.loads(result)
        entry = parsed[0]
        assert entry["id"] == 1
        assert entry["session_id"] == "s1"
        assert entry["module"] == "mod"
        assert entry["node_id"] == "n1"
        assert entry["node_type"] == "ACTION"
        assert entry["outcome"] == "done"
        assert entry["context"] == {"key": "value"}
        assert entry["timestamp"] == "2026-01-01T00:00:00Z"
        assert entry["record_hash"] == "abc123"

    def test_empty_entries(self):
        result = export_json([])
        assert json.loads(result) == []


class TestExportCsv:
    def test_returns_valid_csv(self):
        result = export_csv(_sample_entries())
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2

    def test_header_row(self):
        result = export_csv(_sample_entries())
        first_line = result.split("\n")[0]
        assert "id" in first_line
        assert "session_id" in first_line
        assert "record_hash" in first_line

    def test_context_serialized_as_json(self):
        result = export_csv(_sample_entries())
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        parsed_context = json.loads(row["context"])
        assert parsed_context == {"key": "value"}

    def test_empty_entries(self):
        result = export_csv([])
        lines = result.strip().split("\n")
        assert len(lines) == 1  # Header only
