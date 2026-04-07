"""Storage adapters for case artifacts (uploaded files).

The StorageBackend Protocol is the swap point. v1 ships with
LocalDiskStorage (plaintext on disk under data/uploads/). When the
deployment is hardened to handle real PHI, swap in an
EncryptedDiskStorage or S3Storage adapter — no changes to call sites
or the ArtifactStore.

Per CLAUDE.md non-negotiable #1, the storage layer never sees PII
beyond the file bytes themselves. Filenames are sanitized at the
ingest boundary.
"""

from cen.storage.base import StorageBackend
from cen.storage.local import LocalDiskStorage

__all__ = ["StorageBackend", "LocalDiskStorage"]
