"""LocalDiskStorage — plaintext-on-disk adapter for v1 (synthetic data only).

Files live under {root}/{key} with the key being a UUID hex string.
The adapter is intentionally minimal: no encryption, no compression,
no quotas. Real-PHI deployments must swap in an EncryptedDiskStorage
or S3 adapter — see __init__.py.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


class LocalDiskStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "local-disk"

    def _path(self, key: str) -> Path:
        # Defensive: never let a key escape the root directory.
        safe_key = key.replace("\\", "/").lstrip("/")
        if ".." in safe_key.split("/"):
            raise ValueError(f"Invalid storage key: {key}")
        return self.root / safe_key

    async def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def read(self, key: str) -> bytes:
        path = self._path(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)
