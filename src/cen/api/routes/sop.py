"""SOP ingestion routes — upload, parse, extract, promote.

Pipeline:

    POST /api/sop/upload        -> stores blob, returns SOPRecord (status=uploaded)
    POST /api/sop/{id}/parse    -> sets canonical_md, status=parsed
    POST /api/sop/{id}/extract  -> sets draft_module + validation_issues, status=extracted
    POST /api/sop/{id}/promote  -> writes module file, registers engine, status=promoted

Each step is idempotent: re-running parse or extract overwrites the
prior output. Promote refuses to run when validation issues contain
any error-severity entries.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from cen.api.dependencies import (
    get_current_user,
    get_engines,
    get_event_bus,
    get_llm,
    get_llm_semaphore,
    get_settings,
    get_sop_store,
    get_storage_backend,
)
from cen.config import Settings
from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import AOPDefinition, SOPRecord, User, ValidationIssue
from cen.sop.extractor import RegexExtractor
from cen.sop.parsers import parse_to_markdown
from cen.sop.promoter import PromotionError, promote_draft
from cen.sop.store import SOPStore
from cen.sop.validators import validate_draft
from cen.storage.base import StorageBackend
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import SOPEvent


router = APIRouter(prefix="/sop", tags=["sop"])


# 25 MB cap, matching artifacts. SOPs are typically much smaller.
MAX_SOP_BYTES = 25 * 1024 * 1024

_SOP_CONTENT_TYPES = {
    "text/markdown",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Filename suffixes accepted regardless of declared content type.
# Many browsers send application/octet-stream for .docx and .md; we
# accept those as long as the *extension* is one we know how to parse.
_SOP_EXTENSIONS = (".md", ".markdown", ".docx", ".txt")

_FILENAME_BAD_CHARS = re.compile(r"[\x00-\x1f\\/:*?\"<>|]+")
_NAME_TO_MODULE = re.compile(r"[^a-z0-9]+")


def _sanitize_filename(name: str) -> str:
    cleaned = _FILENAME_BAD_CHARS.sub("_", name).strip()
    if not cleaned:
        cleaned = "sop"
    return cleaned[:200]


def _suggest_module_name(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].lower()
    cleaned = _NAME_TO_MODULE.sub("_", stem).strip("_")
    return cleaned or "sop_module"


async def _emit(event_bus: AsyncEventBus, **kwargs) -> None:
    """Emit an SOPEvent without ever blocking the user mutation."""
    try:
        await event_bus.emit(SOPEvent(**kwargs))
    except Exception:  # noqa: BLE001
        # Telemetry must not break the request — per CLAUDE.md §4.1.
        pass


class PromoteRequest(BaseModel):
    module_name: Optional[str] = None


class ExtractResponse(BaseModel):
    sop: SOPRecord
    draft: AOPDefinition
    validation_issues: List[ValidationIssue]


@router.post("/upload", response_model=SOPRecord, status_code=201)
async def upload_sop(
    file: UploadFile = File(...),
    sop_store: SOPStore = Depends(get_sop_store),
    storage: StorageBackend = Depends(get_storage_backend),
    event_bus: AsyncEventBus = Depends(get_event_bus),
    user: User = Depends(get_current_user),
) -> SOPRecord:
    body = await file.read(MAX_SOP_BYTES + 1)
    if len(body) > MAX_SOP_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"This SOP is larger than {MAX_SOP_BYTES // (1024 * 1024)} MB. "
                "Try a smaller version."
            ),
        )

    content_type = (file.content_type or "application/octet-stream").lower()
    name = (file.filename or "").lower()
    accepted_by_ct = content_type in _SOP_CONTENT_TYPES
    accepted_by_ext = name.endswith(_SOP_EXTENSIONS)
    if not (accepted_by_ct or accepted_by_ext):
        raise HTTPException(
            status_code=415,
            detail="SOP uploads must be Markdown (.md), plain text, or Word (.docx).",
        )

    safe_name = _sanitize_filename(file.filename or "sop")
    storage_key = f"sops/{uuid.uuid4().hex}"
    await storage.write(storage_key, body)

    record = await sop_store.create(
        filename=safe_name,
        content_type=content_type,
        size=len(body),
        storage_key=storage_key,
        owner_id=user.id,
    )
    await _emit(event_bus, sop_id=record.id, stage="uploaded", filename=safe_name)
    return record


@router.get("", response_model=List[SOPRecord])
async def list_sops(
    sop_store: SOPStore = Depends(get_sop_store),
    user: User = Depends(get_current_user),
) -> List[SOPRecord]:
    return await sop_store.list(owner_id=user.id)


@router.get("/{sop_id}", response_model=SOPRecord)
async def get_sop(
    sop_id: str,
    sop_store: SOPStore = Depends(get_sop_store),
    user: User = Depends(get_current_user),
) -> SOPRecord:
    record = await sop_store.get(sop_id)
    if record is None or (record.owner_id and record.owner_id != user.id):
        # Cross-tenant: 404 not 403.
        raise HTTPException(status_code=404, detail="SOP not found")
    return record


@router.post("/{sop_id}/parse", response_model=SOPRecord)
async def parse_sop(
    sop_id: str,
    sop_store: SOPStore = Depends(get_sop_store),
    storage: StorageBackend = Depends(get_storage_backend),
    event_bus: AsyncEventBus = Depends(get_event_bus),
    user: User = Depends(get_current_user),
) -> SOPRecord:
    record = await sop_store.get(sop_id)
    if record is None or (record.owner_id and record.owner_id != user.id):
        raise HTTPException(status_code=404, detail="SOP not found")
    try:
        data = await storage.read(record.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=410, detail="The uploaded SOP is no longer available."
        )
    try:
        canonical = parse_to_markdown(
            filename=record.filename,
            content_type=record.content_type,
            data=data,
        )
    except ValueError as exc:
        await sop_store.update_failed(sop_id)
        await _emit(event_bus, sop_id=sop_id, stage="failed", filename=record.filename)
        raise HTTPException(
            status_code=422,
            detail=f"We couldn't read this SOP: {exc}",
        )
    updated = await sop_store.update_parsed(sop_id, canonical_md=canonical)
    assert updated is not None
    await _emit(event_bus, sop_id=sop_id, stage="parsed", filename=record.filename)
    return updated


@router.post("/{sop_id}/extract", response_model=ExtractResponse)
async def extract_sop(
    sop_id: str,
    sop_store: SOPStore = Depends(get_sop_store),
    event_bus: AsyncEventBus = Depends(get_event_bus),
    user: User = Depends(get_current_user),
) -> ExtractResponse:
    record = await sop_store.get(sop_id)
    if record is None or (record.owner_id and record.owner_id != user.id):
        raise HTTPException(status_code=404, detail="SOP not found")
    if not record.canonical_md:
        raise HTTPException(
            status_code=409,
            detail="Parse the SOP before extraction. Try /api/sop/{id}/parse first.",
        )

    extractor = RegexExtractor()
    suggested = _suggest_module_name(record.filename)
    draft = extractor.extract(
        canonical_md=record.canonical_md,
        sop_id=sop_id,
        suggested_module_name=suggested,
    )
    issues = validate_draft(draft)
    updated = await sop_store.update_extracted(
        sop_id, draft_module=draft, validation_issues=issues
    )
    assert updated is not None
    await _emit(event_bus, sop_id=sop_id, stage="extracted", filename=record.filename)
    return ExtractResponse(sop=updated, draft=draft, validation_issues=issues)


@router.post("/{sop_id}/promote", response_model=SOPRecord)
async def promote_sop(
    sop_id: str,
    payload: PromoteRequest = PromoteRequest(),
    sop_store: SOPStore = Depends(get_sop_store),
    settings: Settings = Depends(get_settings),
    engines: dict = Depends(get_engines),
    llm=Depends(get_llm),
    event_bus: AsyncEventBus = Depends(get_event_bus),
    llm_semaphore=Depends(get_llm_semaphore),
    user: User = Depends(get_current_user),
) -> SOPRecord:
    record = await sop_store.get(sop_id)
    if record is None or (record.owner_id and record.owner_id != user.id):
        raise HTTPException(status_code=404, detail="SOP not found")
    if record.draft_module is None:
        raise HTTPException(
            status_code=409,
            detail="Extract the SOP before promoting. Try /api/sop/{id}/extract first.",
        )

    # Promoted modules land alongside the data directory. When db_path
    # is :memory: (tests), we anchor against uploads_dir instead so the
    # promote path works without touching the real data dir.
    if settings.db_path == ":memory:":
        modules_dir = Path(settings.uploads_dir).resolve().parent / "modules"
    else:
        modules_dir = Path(settings.db_path).resolve().parent / "modules"

    try:
        promoted = promote_draft(
            draft=record.draft_module,
            modules_dir=modules_dir,
            engines=engines,
            llm=llm,
            event_bus=event_bus,
            llm_semaphore=llm_semaphore,
            requested_name=payload.module_name,
        )
    except PromotionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    updated = await sop_store.update_promoted(
        sop_id,
        module_name=promoted.module_name,
        module_version=promoted.version,
    )
    assert updated is not None
    await _emit(
        event_bus,
        sop_id=sop_id,
        stage="promoted",
        filename=record.filename,
        module_name=promoted.module_name,
        module_version=promoted.version,
    )
    return updated


@router.delete("/{sop_id}", status_code=204)
async def delete_sop(
    sop_id: str,
    sop_store: SOPStore = Depends(get_sop_store),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(get_current_user),
) -> None:
    record = await sop_store.get(sop_id)
    if record is None or (record.owner_id and record.owner_id != user.id):
        raise HTTPException(status_code=404, detail="SOP not found")
    try:
        await storage.delete(record.storage_key)
    except Exception:  # noqa: BLE001
        pass
    await sop_store.delete(sop_id)
