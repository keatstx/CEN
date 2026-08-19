"""Model preference resolution — surviving provider retirements.

CEN was pinned to a single hardcoded model id. When Groq retired
llama-3.3-70b-versatile on 2026-08-16 there was no second choice to
fall back to, so every completion failed. The information needed to
self-heal was one HTTP call away the whole time: /models is
machine-readable and authoritative about what a provider still offers.

So ``CEN_LLM_MODEL`` now accepts an ordered preference list:

    CEN_LLM_MODEL=openai/gpt-oss-20b,openai/gpt-oss-120b

The first preference the provider actually offers wins. A retirement
becomes a log line and a slightly different model instead of an
outage, and the ranking decision gets made in advance — with time to
think — rather than under pressure after something breaks.

What this deliberately does NOT do is pick a model by heuristic
("largest available"). Availability is machine-checkable; quality
equivalence is not. For a compliance product, a heuristic silently
choosing which model drafts a patient's appeal letter is bad
governance. A human ranks the list; the resolver only ever picks from
that list.

Note the resolver cannot save you from letting the list go stale — if
every preference is eventually retired there is nothing left to pick.
That is a quarterly glance at the provider's model list, not a fire
drill.
"""

from __future__ import annotations

from typing import Iterable, List, Optional


def parse_preferences(raw: str) -> List[str]:
    """Split a configured model value into an ordered preference list.

    Accepts a single id ("phi3:mini") or a comma-separated list, so
    existing single-model configuration keeps working untouched.
    Order is preserved and duplicates are dropped — the order *is* the
    policy.
    """
    if not raw:
        return []
    out: List[str] = []
    for part in raw.split(","):
        candidate = part.strip()
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def choose_model(
    preferences: Iterable[str], offered: Optional[Iterable[str]]
) -> Optional[str]:
    """The highest-ranked preference the provider still offers.

    ``offered`` is what /models reported. When it is None or empty the
    provider doesn't enumerate its models (some OpenAI-compatible
    servers don't), so we can't verify anything — take the top
    preference and let the call itself be the test.

    Returns None when the provider enumerates its models and offers
    none of the preferences. That is the "your whole list is retired"
    case, and it must be loud rather than silently papered over.
    """
    ranked = list(preferences)
    if not ranked:
        return None
    available = {m for m in (offered or []) if m}
    if not available:
        return ranked[0]
    for candidate in ranked:
        if candidate in available:
            return candidate
    return None
