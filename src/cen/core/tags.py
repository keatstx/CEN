"""Tag vocabulary + helpers for namespaced step/FAQ tags.

A tag is ``"<facet>:<value>"`` (e.g. ``"function:eligibility_check"``).
The vocabulary lists controlled facets and their known values; the
``attribute`` facet is open. Everything here is pure/stdlib so the
extractor, validator, and retrieval path can all share it without a
DB round-trip. The vocabulary is a seed JSON today; it moves to a
per-project table when multi-org lands (see tag_vocabulary.json).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

_VOCAB_PATH = Path(__file__).resolve().parent.parent / "seed" / "tag_vocabulary.json"

# Facets that accept any value (long-tail); never flagged for unknown values.
_OPEN_FACETS = {"attribute"}


@lru_cache(maxsize=1)
def _load_vocabulary() -> Dict[str, List[str]]:
    try:
        data = json.loads(_VOCAB_PATH.read_text(encoding="utf-8"))
        return dict(data.get("facets", {}))
    except (OSError, json.JSONDecodeError):
        return {}


def vocabulary() -> Dict[str, List[str]]:
    """Public read of the tag vocabulary — facet -> known values.

    The ``attribute`` facet is present with an empty list (open-ended).
    Consumed by the authoring UI for tag autocomplete.
    """
    return dict(_load_vocabulary())


def parse_tag(tag: str) -> Tuple[str, str]:
    """Split ``"facet:value"`` into (facet, value). A tag with no colon
    is treated as facet="" so callers can flag malformed tags."""
    if ":" not in tag:
        return "", tag
    facet, value = tag.split(":", 1)
    return facet.strip(), value.strip()


def facet_of(tag: str) -> str:
    return parse_tag(tag)[0]


def is_known_tag(tag: str) -> bool:
    """True if the tag is well-formed and within the vocabulary.

    Open facets (attribute) accept any value. Unknown facets or unknown
    values under a controlled facet return False — the validator turns
    that into a warning, not a hard error.
    """
    facet, value = parse_tag(tag)
    if not facet or not value:
        return False
    if facet in _OPEN_FACETS:
        return True
    vocab = _load_vocabulary()
    if facet not in vocab:
        return False
    return value in vocab[facet]


def unknown_tags(tags: List[str]) -> List[str]:
    """Return the subset of tags not recognized by the vocabulary."""
    return [t for t in tags if not is_known_tag(t)]


def tag_overlap(a: List[str], b: List[str]) -> int:
    """Count of shared tags between two tag lists."""
    return len(set(a) & set(b))
