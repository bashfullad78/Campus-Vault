"""Storage interface: the contract note logic programs against."""

import re
from typing import BinaryIO, Protocol, runtime_checkable

# Keys look like "notes/2026/09/<64-hex>.pdf" — nothing else is accepted.
# Months restricted to 01-12: keys are server-generated, so the pattern can
# be as strict as the generator. Shared by every backend so the contract is
# identical regardless of where bytes land.
_KEY_PATTERN = re.compile(r"^notes/\d{4}/(0[1-9]|1[0-2])/[0-9a-f]{64}\.pdf$")


class StorageError(Exception):
    """Raised when a file cannot be stored, read, or deleted."""


def validate_key(key: str) -> str:
    """Return `key` if it matches the server-generated pattern; raise otherwise."""
    if not _KEY_PATTERN.match(key):
        raise StorageError(f"invalid storage key: {key!r}")
    return key


def safe_close(fileobj: object) -> None:
    """Best-effort close for cleanup paths that may run after a failure."""
    close = getattr(fileobj, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001 — cleanup must never mask the real error
            pass


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal protocol for persisting immutable note files.

    Implementations receive an already-validated, server-named storage key and
    must never derive paths from user input (path-traversal defense, §11).
    """

    def save(self, key: str, fileobj: BinaryIO) -> None:
        """Persist the stream under `key`. Raises StorageError on failure."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Return a readable binary stream for `key`. Raises StorageError if absent."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object at `key`. Must not raise if it is already gone."""
        ...
