"""Promote a draft AOPDefinition into a versioned, runnable module.

Refuses to promote when validation has any error-severity issues.
Writes the JSON to `data/modules/<name>_v<version>.json`, registers a
new engine in the live module registry, and returns the version that
was assigned.

Versioning: if the requested module name already exists, the version
is bumped (1.0 -> 1.1 -> 1.2 ...). Existing in-flight cases pinned to
older versions are unaffected because Session.module_version is set at
creation (Non-Negotiable #4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from cen.core.engine import AsyncWorkflowEngine
from cen.core.exceptions import CycleDetectedError
from cen.core.models import AOPDefinition
from cen.sop.validators import has_blocking_errors, validate_draft


class PromotionError(Exception):
    """Raised when a draft cannot be promoted (validation errors)."""


def promote_draft(
    *,
    draft: AOPDefinition,
    modules_dir: Path,
    engines: dict[str, AsyncWorkflowEngine],
    llm,
    event_bus,
    llm_semaphore,
    scrubber=None,
    requested_name: Optional[str] = None,
) -> AOPDefinition:
    """Persist `draft` to disk and register it in the live engine map.

    Returns the promoted AOPDefinition (with its assigned version).
    Raises PromotionError if validation has blocking errors.
    """
    issues = validate_draft(draft)
    if has_blocking_errors(issues):
        blockers = [i for i in issues if i.severity == "error"]
        raise PromotionError(
            "Draft has validation errors and cannot be promoted: "
            + "; ".join(f"{i.node_id or '-'}: {i.message}" for i in blockers)
        )

    module_name = requested_name or draft.module_name
    version = _next_version(module_name, modules_dir)

    promoted = draft.model_copy(update={"module_name": module_name, "version": version})

    modules_dir.mkdir(parents=True, exist_ok=True)
    path = modules_dir / f"{module_name}_v{version}.json"
    path.write_text(json.dumps(promoted.model_dump(), indent=2), encoding="utf-8")

    engine = AsyncWorkflowEngine(
        llm=llm, event_bus=event_bus, llm_semaphore=llm_semaphore, scrubber=scrubber
    )
    try:
        engine.load_aop(promoted)
    except CycleDetectedError as exc:
        # Validator should catch this first, but defend in depth in case
        # an LLM-extracted draft slips through with a cycle.
        path.unlink(missing_ok=True)
        raise PromotionError(
            "This workflow contains a loop. The current engine doesn't support "
            "looping workflows — break the loop in the review UI and try again."
        ) from exc
    engines[module_name] = engine

    return promoted


def _next_version(module_name: str, modules_dir: Path) -> str:
    """Pick the next version string for a module name.

    Existing files: <name>_v1.0.json, <name>_v1.1.json, ...
    Returns "1.0" if no prior versions exist.
    """
    if not modules_dir.exists():
        return "1.0"
    prefix = f"{module_name}_v"
    versions: list[tuple[int, int]] = []
    for path in modules_dir.glob(f"{prefix}*.json"):
        stem = path.stem  # <name>_v1.2
        try:
            ver = stem.split("_v", 1)[1]
            major, minor = ver.split(".")
            versions.append((int(major), int(minor)))
        except (ValueError, IndexError):
            continue
    if not versions:
        return "1.0"
    major, minor = max(versions)
    return f"{major}.{minor + 1}"
