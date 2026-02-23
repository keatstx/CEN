"""Pure export functions for audit trail entries."""

from __future__ import annotations

import csv
import io
import json
from typing import List

from cen.core.models import AuditEntry


def export_json(entries: List[AuditEntry]) -> str:
    """Serialize audit entries to a JSON string."""
    return json.dumps([e.model_dump() for e in entries], indent=2)


def export_csv(entries: List[AuditEntry]) -> str:
    """Serialize audit entries to a CSV string."""
    output = io.StringIO()
    fieldnames = [
        "id", "session_id", "module", "node_id", "node_type",
        "outcome", "context", "timestamp", "record_hash",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for entry in entries:
        row = entry.model_dump()
        row["context"] = json.dumps(row["context"])
        writer.writerow(row)
    return output.getvalue()
