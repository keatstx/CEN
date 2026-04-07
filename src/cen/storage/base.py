"""StorageBackend Protocol — the swap point for upload storage adapters."""

from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """All storage adapters must implement this interface.

    The backend stores blobs by an opaque key returned at write time.
    The ArtifactStore tracks the key in the database alongside the
    user-facing metadata (filename, content type, size).
    """

    async def write(self, key: str, data: bytes) -> None:
        """Persist blob data under the given key. Implementations are
        responsible for any encryption, compression, or remote upload."""

    async def read(self, key: str) -> bytes:
        """Return the blob bytes for the given key. Raises FileNotFoundError
        if the key does not exist."""

    async def delete(self, key: str) -> None:
        """Remove the blob. Idempotent — deleting a missing key is OK."""

    @property
    def backend_name(self) -> str:
        """Identifier for telemetry / health output."""
