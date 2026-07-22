"""Extract structured input suggestions from a chat conversation.

When the user types something like "the family earns about $32k for a
household of three" mid-chat, we want to surface
`{income_fpl_percent: ~125, household_size: 3}` as one-tap
suggestions in the StepCard.

The extractor is intentionally rule-based for v1:
- Deterministic, testable, no LLM tokens.
- Scoped to the current step's `input_schema` so we only extract for
  fields the user is *about* to fill.
- Each suggestion carries `confidence` and `evidence` so the UI can
  surface the source ("from your chat: 'family of three'").

A `SuggestionExtractor` Protocol is defined for the future LLM swap;
the rule-based `RegexExtractor` is the v1 implementation.

The extractor never writes to context. Suggestions surface in
`ConciergeResponse.suggested_inputs`; applying them goes through the
existing `provide_input` route so the audit chain stays unbroken
(Non-Negotiable #2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Protocol

from cen.core.models import ChatMessage, InputField, SuggestedInput


@dataclass
class _Match:
    """Internal match result with confidence + evidence."""

    value: Any
    confidence: float
    evidence: str


class SuggestionExtractor(Protocol):
    """Strategy interface — turns chat history + an input schema into
    a list of suggested values. Implementations: RegexExtractor (v1),
    LLMExtractor (later)."""

    def extract(
        self,
        *,
        history: List[ChatMessage],
        input_schema: List[InputField],
    ) -> List[SuggestedInput]: ...

    @property
    def extractor_name(self) -> str: ...


# ── Regex / keyword patterns ─────────────────────────────────────────


_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"

# Money: "$32,000", "$32k", "32k", "$1.2 million", "1.2m"
_MONEY = re.compile(
    rf"\$?\s*{_NUMBER}\s*(k|thousand|m|million)?",
    re.IGNORECASE,
)

# Household size: "family of 4", "household of three", "4 people",
# "3 children", "3-person household"
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_HOUSEHOLD_SIZE = re.compile(
    r"(?:family|household)\s+of\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")"
    r"|(\d+)[-\s]*(?:person|people|members?)\s+(?:family|household)",
    re.IGNORECASE,
)

# FPL percentage: "200% FPL", "150 percent of poverty", "above 200%"
_FPL_PCT = re.compile(
    r"(\d{2,3})\s*(?:%|percent)\s*(?:of\s+)?(?:fpl|poverty|federal\s+poverty)",
    re.IGNORECASE,
)

# ZIP code: 5 digits, optionally with a 4-digit extension
_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

# Yes/no boolean: explicit affirmation/denial
_YES_PATTERNS = re.compile(
    r"\b(yes|yeah|yep|correct|that'?s right|absolutely|definitely)\b",
    re.IGNORECASE,
)
_NO_PATTERNS = re.compile(
    r"\b(no|nope|not really|negative|absolutely not|definitely not)\b",
    re.IGNORECASE,
)

# Dates: ISO (2026-01-15 — what <input type="date"> emits), US numeric
# (01/15/2026, 1-15-26), and long (January 15 2026). All are normalized
# to ISO YYYY-MM-DD before suggesting, since the date field can only
# consume ISO.
_DATE_ISO = re.compile(r"\b(\d{4}-\d{1,2}-\d{1,2})\b")
_DATE_NUMERIC = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")
_DATE_LONG = re.compile(
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)


# ── Extractor implementation ─────────────────────────────────────────


class RegexExtractor:
    """Deterministic keyword + regex extractor.

    Walks user messages newest-first (most recent statement wins) and
    matches each input-schema field against patterns picked by the
    field's `type` and `key`.
    """

    extractor_name = "regex.v1"

    def extract(
        self,
        *,
        history: List[ChatMessage],
        input_schema: List[InputField],
    ) -> List[SuggestedInput]:
        if not history or not input_schema:
            return []
        # Only extract from user turns (don't echo the assistant's own
        # words back as a suggestion). Newest-first: recent statements
        # override stale ones.
        user_text_chunks = [
            m.content for m in reversed(history) if m.role == "user"
        ]
        if not user_text_chunks:
            return []

        suggestions: list[SuggestedInput] = []
        for field in input_schema:
            match = _extract_field(field, user_text_chunks)
            if match is not None:
                suggestions.append(
                    SuggestedInput(
                        key=field.key,
                        value=match.value,
                        confidence=match.confidence,
                        evidence=match.evidence,
                        source="chat",
                    )
                )
        return suggestions


def _extract_field(
    field: InputField, user_chunks: List[str]
) -> Optional[_Match]:
    key = field.key.lower()
    label = field.label.lower()
    ftype = field.type

    # Field-key heuristics first — these are CEN-specific and high-confidence.
    if "household_size" in key or "family_size" in key:
        return _match_household_size(user_chunks)
    if "fpl_percent" in key or "fpl_percentage" in key or "fpl" in key:
        return _match_fpl_percent(user_chunks)
    if "income" in key or "income" in label:
        return _match_income(user_chunks)
    if "zip_code" in key or "zip" in key or "postal" in key:
        return _match_zip(user_chunks)

    # Generic type-based fallback.
    if ftype == "boolean":
        return _match_boolean(user_chunks)
    if ftype == "currency":
        return _match_money(user_chunks)
    if ftype == "number":
        return _match_first_number(user_chunks)
    if ftype == "date":
        return _match_date(user_chunks)
    if ftype == "select":
        return _match_select(user_chunks, field.options or [])

    # Free-text fields: don't guess. Leave for the LLM extractor.
    return None


# ── Field-specific matchers ──────────────────────────────────────────


def _match_household_size(chunks: List[str]) -> Optional[_Match]:
    for chunk in chunks:
        m = _HOUSEHOLD_SIZE.search(chunk)
        if not m:
            continue
        # Group 1 is "family of X"; group 2 is "X-person household".
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        value = _NUMBER_WORDS.get(raw.lower())
        if value is None:
            try:
                value = int(raw)
            except ValueError:
                continue
        if 1 <= value <= 20:
            return _Match(
                value=value,
                confidence=0.85,
                evidence=_short_excerpt(chunk, m.start(), m.end()),
            )
    return None


def _match_fpl_percent(chunks: List[str]) -> Optional[_Match]:
    """Extract an FPL percentage from explicit phrasing or derive it
    from income + household size when both are known."""
    for chunk in chunks:
        m = _FPL_PCT.search(chunk)
        if not m:
            continue
        try:
            pct = int(m.group(1))
        except ValueError:
            continue
        if 0 < pct < 1000:
            return _Match(
                value=pct,
                confidence=0.9,
                evidence=_short_excerpt(chunk, m.start(), m.end()),
            )
    # Derived path: income + household size → FPL percentage. Skipped
    # for v1 because the FPL grid lives in the workflow, not here.
    # Documented as a future enhancement.
    return None


def _match_income(chunks: List[str]) -> Optional[_Match]:
    for chunk in chunks:
        m = _MONEY.search(chunk)
        if not m:
            continue
        amount = _money_to_int(m.group(1), m.group(2))
        if amount is None:
            continue
        if 1_000 <= amount <= 10_000_000:
            return _Match(
                value=amount,
                confidence=0.7,
                evidence=_short_excerpt(chunk, m.start(), m.end()),
            )
    return None


def _match_money(chunks: List[str]) -> Optional[_Match]:
    return _match_income(chunks)


def _match_zip(chunks: List[str]) -> Optional[_Match]:
    for chunk in chunks:
        m = _ZIP.search(chunk)
        if m:
            return _Match(
                value=m.group(1),
                confidence=0.95,
                evidence=_short_excerpt(chunk, m.start(), m.end()),
            )
    return None


def _match_boolean(chunks: List[str]) -> Optional[_Match]:
    # Boolean extraction from chat is risky — "yes" might refer to a
    # prior question, not the current field. Only trust the most
    # recent message and only if it's a clear standalone affirmation.
    if not chunks:
        return None
    latest = chunks[0].strip()
    if len(latest) > 80:
        # Long messages need an LLM to disambiguate.
        return None
    if _YES_PATTERNS.search(latest):
        return _Match(value=True, confidence=0.6, evidence=latest)
    if _NO_PATTERNS.search(latest):
        return _Match(value=False, confidence=0.6, evidence=latest)
    return None


def _match_first_number(chunks: List[str]) -> Optional[_Match]:
    for chunk in chunks:
        m = re.search(rf"\b{_NUMBER}\b", chunk)
        if not m:
            continue
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        return _Match(
            value=int(value) if value.is_integer() else value,
            confidence=0.5,
            evidence=_short_excerpt(chunk, m.start(), m.end()),
        )
    return None


def _match_date(chunks: List[str]) -> Optional[_Match]:
    for chunk in chunks:
        for pattern in (_DATE_ISO, _DATE_NUMERIC, _DATE_LONG):
            m = pattern.search(chunk)
            if not m:
                continue
            iso = _normalize_date(m.group(1))
            if iso is None:
                continue
            return _Match(
                value=iso,  # always ISO YYYY-MM-DD — what the date field expects
                confidence=0.7,
                evidence=_short_excerpt(chunk, m.start(), m.end()),
            )
    return None


def _normalize_date(raw: str) -> Optional[str]:
    """Parse a matched date string into ISO YYYY-MM-DD. Handles ISO,
    US M/D/Y (2- and 4-digit years), and long month-name forms. Returns
    None if no known format parses (caller skips the suggestion)."""
    cleaned = raw.strip().replace(",", "").replace(".", "")
    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y", "%m-%d-%Y",
        "%m/%d/%y", "%m-%d-%y",
        "%B %d %Y", "%b %d %Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _match_select(
    chunks: List[str], options: List[dict]
) -> Optional[_Match]:
    """Match a select option by literal keyword presence."""
    for chunk in chunks:
        text = chunk.lower()
        for opt in options:
            value = opt.get("value", "")
            label = opt.get("label", "")
            if value and value.lower() in text:
                return _Match(value=value, confidence=0.7, evidence=chunk[:80])
            if label and label.lower() in text:
                return _Match(value=value, confidence=0.7, evidence=chunk[:80])
    return None


# ── Helpers ──────────────────────────────────────────────────────────


def _money_to_int(raw: str, suffix: Optional[str]) -> Optional[int]:
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        s = suffix.lower()
        if s in {"k", "thousand"}:
            value *= 1_000
        elif s in {"m", "million"}:
            value *= 1_000_000
    return int(value)


def _short_excerpt(chunk: str, start: int, end: int) -> str:
    """Return a tight excerpt around the match for the suggestion UI."""
    pad = 20
    s = max(0, start - pad)
    e = min(len(chunk), end + pad)
    snippet = chunk[s:e].strip()
    if s > 0:
        snippet = "…" + snippet
    if e < len(chunk):
        snippet = snippet + "…"
    return snippet
