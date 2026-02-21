"""PII scrubbing — regex tier + optional Presidio NER."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Common PII patterns
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

REDACTED = "[REDACTED]"


@runtime_checkable
class PIIScrubber(Protocol):
    def scrub(self, text: str) -> str: ...


class RegexPIIScrubber:
    """Fast regex-based PII redaction for SSN, phone, and email."""

    def scrub(self, text: str) -> str:
        text = _SSN_RE.sub(REDACTED, text)
        text = _PHONE_RE.sub(REDACTED, text)
        text = _EMAIL_RE.sub(REDACTED, text)
        return text


class PresidioPIIScrubber:
    """NER-powered PII redaction via Microsoft Presidio."""

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-untyped]
        from presidio_anonymizer import AnonymizerEngine  # type: ignore[import-untyped]

        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()

    def scrub(self, text: str) -> str:
        results = self._analyzer.analyze(text=text, language="en")
        anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text


def create_scrubber(backend: str = "regex") -> PIIScrubber:
    if backend == "presidio":
        return PresidioPIIScrubber()
    return RegexPIIScrubber()
