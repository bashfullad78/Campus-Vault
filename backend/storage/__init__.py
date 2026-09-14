"""Storage backend abstraction (vision.txt §7: storage/).

Note logic depends only on the StorageBackend protocol, so the V1 local
filesystem backend can be swapped for an S3 backend without touching
note-management code. Selection is configuration-driven (STORAGE_BACKEND),
happens once per process, and — for S3 — proves credentials/bucket work at
boot so a misconfigured deploy fails loudly instead of at first upload.
"""

import logging
import threading

from .interface import StorageBackend, StorageError
from .local import LocalStorage
from .s3 import S3Storage

__all__ = [
    "StorageBackend",
    "StorageError",
    "LocalStorage",
    "S3Storage",
    "get_storage",
]

logger = logging.getLogger(__name__)

_storage: StorageBackend | None = None
_lock = threading.Lock()


def _build() -> StorageBackend:
    from backend.config import settings  # local import: avoids config/import cycles

    if settings.STORAGE_BACKEND == "s3":
        backend: StorageBackend = S3Storage(
            bucket=settings.S3_BUCKET,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
        )
        backend.boot_check()  # fail the deploy, not the first upload
        return backend
    return LocalStorage(settings.STORAGE_DIR)


def get_storage() -> StorageBackend:
    """Process-wide storage backend, built lazily and exactly once.

    Replaces the per-request construction the routes used before: S3 clients
    hold connection pools, and boot_check must not run per request. Thread-safe
    so concurrent first requests cannot race the initialization.
    """
    global _storage
    if _storage is None:
        with _lock:
            if _storage is None:  # double-checked; the lock is only hit once
                _storage = _build()
                logger.info("Storage backend ready: %s", type(_storage).__name__)
    return _storage


def reset_storage() -> None:
    """Drop the cached backend (tests and config-swap scenarios only)."""
    global _storage
    with _lock:
        _storage = None
