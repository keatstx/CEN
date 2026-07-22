"""LLM-backed suggestion extractor (the v2 the RegexExtractor deferred to).

Free-text fields — patient name, provider, plan name — can't be pulled
from chat by regex, so they never populated the center step. This
extractor closes that gap: it runs the deterministic RegexExtractor
first (trusted for structured fields: income, household, dates, zip,
booleans, selects), then asks the LLM to fill only the fields regex
couldn't. On any LLM failure it returns the regex result, so it never
does worse than v1.

Compliance: the chat text is PII-scrubbed before it reaches the LLM
(Non-Negotiable #1), same as GENERATE and the concierge prompt path.
With the default regex scrubber, ordinary names pass through (they're
not in the wordlist) so extraction works; a future Presidio deployment
that redacts names would degrade name extraction — the same tension
GENERATE has, resolved at the deployment/BAA policy level, not here.
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional

from cen.core.models import ChatMessage, InputField, SuggestedInput
from cen.core.suggestions import RegexExtractor

_LLM_CONFIDENCE = 0.8  # above ChatLedStep's 0.5 auto-apply threshold
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class LLMExtractor:
    """Regex-first, LLM-fills-the-gaps suggestion extractor."""

    extractor_name = "llm.v1"

    def __init__(self, *, llm: Any, scrubber: Optional[Any] = None) -> None:
        self._llm = llm
        self._scrubber = scrubber
        self._regex = RegexExtractor()

    async def extract(
        self,
        *,
        history: List[ChatMessage],
        input_schema: List[InputField],
    ) -> List[SuggestedInput]:
        regex_out = self._regex.extract(history=history, input_schema=input_schema)
        covered = {s.key for s in regex_out}
        gaps = [f for f in input_schema if f.key not in covered]
        if not gaps:
            return regex_out

        user_msgs = [m.content for m in history if m.role == "user"]
        if not user_msgs:
            return regex_out

        try:
            filled = await self._llm_fill(user_msgs, gaps)
        except Exception:
            return regex_out  # never worse than regex

        # Regex wins for what it found; LLM only fills the gaps.
        by_key = {s.key: s for s in regex_out}
        for s in filled:
            by_key.setdefault(s.key, s)
        return list(by_key.values())

    async def _llm_fill(
        self, user_msgs: List[str], gaps: List[InputField]
    ) -> List[SuggestedInput]:
        prompt = self._build_prompt(user_msgs, gaps)
        if self._scrubber is not None:
            prompt = self._scrubber.scrub(prompt)
        raw = await self._llm.generate(prompt, max_tokens=200)
        parsed = self._parse_json(raw)
        gap_by_key = {f.key: f for f in gaps}
        out: List[SuggestedInput] = []
        for key, value in parsed.items():
            field = gap_by_key.get(key)
            if field is None:
                continue  # never invent a field the schema didn't ask for
            coerced = _coerce(value, field.type)
            if coerced is None or coerced == "":
                continue
            out.append(
                SuggestedInput(
                    key=key,
                    value=coerced,
                    confidence=_LLM_CONFIDENCE,
                    evidence="AI-read from your chat",
                    source="chat",
                )
            )
        return out

    @staticmethod
    def _build_prompt(user_msgs: List[str], gaps: List[InputField]) -> str:
        field_lines = []
        for f in gaps:
            extra = " (format YYYY-MM-DD)" if f.type == "date" else ""
            desc = f" — {f.description}" if f.description else ""
            field_lines.append(f'- "{f.key}" ({f.label}, type {f.type}{extra}){desc}')
        msgs = "\n".join(f"- {m}" for m in user_msgs[-6:])
        return (
            "Extract form field values from what a navigator typed in chat.\n"
            "Only include a field if its value is clearly stated. Omit anything "
            "uncertain.\n\n"
            "Fields:\n" + "\n".join(field_lines) + "\n\n"
            "Chat messages:\n" + msgs + "\n\n"
            'Return ONLY a JSON object mapping field key to value, e.g. '
            '{"patient_name": "Maria Lopez"}. Dates must be YYYY-MM-DD. '
            "No prose, JSON only."
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        m = _JSON_BLOCK.search(raw or "")
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


def _coerce(value: Any, ftype: str) -> Any:
    """Minimal type coercion; return None to drop an unusable value."""
    if value is None:
        return None
    if ftype == "boolean":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in {"true", "yes", "y", "1"}:
            return True
        if s in {"false", "no", "n", "0"}:
            return False
        return None
    if ftype in {"number", "currency"}:
        try:
            num = float(str(value).replace(",", "").replace("$", "").strip())
            return int(num) if num.is_integer() else num
        except ValueError:
            return None
    return str(value).strip()
