"""Sanitize dicts before telemetry emission — scrubs PII from string values."""

from __future__ import annotations

from typing import Any

from cen.privacy.pii_scrubber import PIIScrubber


def sanitize_context(data: dict[str, Any], scrubber: PIIScrubber) -> dict[str, Any]:
    """Return a shallow copy of *data* with all string values PII-scrubbed."""
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = scrubber.scrub(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_context(value, scrubber)
        else:
            sanitized[key] = value
    return sanitized
