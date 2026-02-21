"""Tests for PII scrubbing."""

from __future__ import annotations

from cen.privacy.pii_scrubber import RegexPIIScrubber, create_scrubber
from cen.privacy.sanitizer import sanitize_context


class TestRegexPIIScrubber:
    def test_scrubs_ssn(self):
        scrubber = RegexPIIScrubber()
        assert "[REDACTED]" in scrubber.scrub("SSN is 123-45-6789")

    def test_scrubs_phone(self):
        scrubber = RegexPIIScrubber()
        assert "[REDACTED]" in scrubber.scrub("Call 555-123-4567")

    def test_scrubs_email(self):
        scrubber = RegexPIIScrubber()
        assert "[REDACTED]" in scrubber.scrub("Email: user@example.com")

    def test_passthrough_clean(self):
        scrubber = RegexPIIScrubber()
        clean = "No PII here, just workflow data"
        assert scrubber.scrub(clean) == clean


class TestSanitizeContext:
    def test_sanitizes_nested_dict(self):
        scrubber = RegexPIIScrubber()
        data = {
            "name": "Patient has SSN 123-45-6789",
            "count": 42,
            "nested": {"phone": "Call 555-123-4567"},
        }
        result = sanitize_context(data, scrubber)
        assert "123-45-6789" not in result["name"]
        assert result["count"] == 42
        assert "555-123-4567" not in result["nested"]["phone"]


class TestCreateScrubber:
    def test_regex_default(self):
        scrubber = create_scrubber("regex")
        assert isinstance(scrubber, RegexPIIScrubber)
