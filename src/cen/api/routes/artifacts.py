"""Case artifact upload + download routes.

v1 ships with conservative defaults — these are the hardening hooks
that lock the upload boundary even though the deployment is synthetic
data only:

- 25 MB hard size cap (server-side, not just a client hint).
- Content-type whitelist with magic-byte sniff on the first 8 bytes
  to defeat mismatched-extension attacks.
- Filename sanitization (strips path separators, control chars, length
  caps at 200).
- Authorization on download: only the case owner can read.
- The actual storage backend is pluggable via cen.storage; v1 uses
  LocalDiskStorage. Encryption-at-rest swap is one config change.
"""

from __future__ import annotations

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from cen.api.dependencies import (
    get_artifact_store,
    get_current_user,
    get_session_store,
    get_storage_backend,
)
from cen.core.artifact_store import ArtifactStore
from cen.core.exceptions import SessionNotFoundError
from cen.core.models import Artifact, User
from cen.core.session_store import SessionStore
from cen.storage.base import StorageBackend


# 25 MB cap. Real-PHI deployments may want smaller — change here.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Whitelist of accepted content types. Each maps to one or more
# acceptable magic-byte prefixes. Use bytes("") for "no sniff —
# accept whatever the client claims" (only safe for plain text).
_MAGIC: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/heic": [b"ftypheic", b"ftypheix", b"ftypmif1"],  # offset 4
    "image/tiff": [b"II*\x00", b"MM\x00*"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",  # DOCX is a ZIP
    ],
    "text/plain": [b""],
}

ALLOWED_CONTENT_TYPES = set(_MAGIC.keys())

_FILENAME_BAD_CHARS = re.compile(r"[\x00-\x1f\\/:*?\"<>|]+")


def _sanitize_filename(name: str) -> str:
    """Strip path separators, control chars, and cap at 200 chars."""
    cleaned = _FILENAME_BAD_CHARS.sub("_", name).strip()
    if not cleaned:
        cleaned = "upload"
    return cleaned[:200]


def _sniff_magic(data: bytes, content_type: str) -> bool:
    """Return True if the file's first bytes match a known magic prefix
    for the declared content type. text/plain is allowed without sniffing."""
    prefixes = _MAGIC.get(content_type, [])
    if prefixes == [b""]:
        return True
    # HEIC magic bytes live at offset 4 (after the size field).
    if content_type == "image/heic":
        if len(data) < 12:
            return False
        ftype_box = data[4:12]
        return any(p in ftype_box for p in prefixes)
    return any(data.startswith(p) for p in prefixes)


router = APIRouter(tags=["artifacts"])


@router.post(
    "/cases/{case_id}/artifacts",
    response_model=Artifact,
    status_code=201,
)
async def upload_artifact(
    case_id: str,
    file: UploadFile = File(...),
    node_id: Optional[str] = Form(default=None),
    case_store: SessionStore = Depends(get_session_store),
    artifact_store: ArtifactStore = Depends(get_artifact_store),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(get_current_user),
) -> Artifact:
    case = await case_store.get(case_id)
    if case is None:
        raise SessionNotFoundError(case_id)
    if case.owner_id is not None and case.owner_id != user.id:
        # Cross-tenant: 404 not 403 (don't leak existence)
        raise SessionNotFoundError(case_id)

    # Read the file body. UploadFile.read() with no arg slurps the
    # whole thing — bounded by MAX_UPLOAD_BYTES below.
    body = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                "Try a smaller version."
            ),
        )

    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"This file type isn't supported. "
                f"Allowed types: PDF, JPG, PNG, HEIC, TIFF, GIF, DOCX, plain text."
            ),
        )
    if not _sniff_magic(body, content_type):
        raise HTTPException(
            status_code=415,
            detail=(
                "This file's contents don't match its type. "
                "Please re-upload as a real PDF, image, or DOCX."
            ),
        )

    safe_name = _sanitize_filename(file.filename or "upload")

    # Storage key: project_id/case_id/artifact_uuid (or root/case_id/...
    # when there's no project). Predictable enough for ops, opaque
    # enough that there's no PII in the path.
    artifact_uuid = uuid.uuid4().hex
    project_segment = case.project_id or "no_project"
    storage_key = f"{project_segment}/{case_id}/{artifact_uuid}"

    await storage.write(storage_key, body)

    artifact = await artifact_store.create(
        case_id=case_id,
        project_id=case.project_id,
        node_id=node_id,
        filename=safe_name,
        content_type=content_type,
        size=len(body),
        storage_key=storage_key,
        owner_id=user.id,
    )
    return artifact


@router.get("/cases/{case_id}/artifacts", response_model=list[Artifact])
async def list_case_artifacts(
    case_id: str,
    case_store: SessionStore = Depends(get_session_store),
    artifact_store: ArtifactStore = Depends(get_artifact_store),
    user: User = Depends(get_current_user),
) -> List[Artifact]:
    case = await case_store.get(case_id)
    if case is None:
        raise SessionNotFoundError(case_id)
    if case.owner_id is not None and case.owner_id != user.id:
        raise SessionNotFoundError(case_id)
    return await artifact_store.list_for_case(case_id, owner_id=user.id)


@router.get("/artifacts/{artifact_id}")
async def download_artifact(
    artifact_id: str,
    artifact_store: ArtifactStore = Depends(get_artifact_store),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(get_current_user),
) -> Response:
    artifact = await artifact_store.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.owner_id is not None and artifact.owner_id != user.id:
        # Cross-tenant download attempt — 404 not 403.
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        data = await storage.read(artifact.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=410,
            detail="The file is no longer available on the server.",
        )

    return Response(
        content=data,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Cache-Control": "private, no-store",
        },
    )
