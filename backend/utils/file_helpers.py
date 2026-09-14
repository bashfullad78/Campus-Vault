"""PDF validation pipeline and storage-key generation (vision.txt V1: File Validation).

Pipeline: size → magic bytes → PDF parsing → page count → encryption → SHA-256.
Every check is server-side; the client is never trusted (vision.txt §12).

The full file is streamed exactly once: chunks update the SHA-256 hasher and a
spooled temp file simultaneously. Validation re-reads the temp file, and the
caller passes that same spooled file to storage, so the user-supplied stream
and its filename never touch storage paths (path-traversal defense, §11).
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO
from tempfile import SpooledTemporaryFile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.config import settings

# Chunks larger than this spill to disk instead of RAM.
_SPOOL_THRESHOLD_BYTES = 1 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024

PDF_MAGIC = b"%PDF-"


class FileValidationError(Exception):
    """Base class for every upload-validation failure."""


class FileTooLargeError(FileValidationError):
    pass


class NotAPdfError(FileValidationError):
    pass


class InvalidPdfError(FileValidationError):
    pass


class PageCountError(FileValidationError):
    pass


class EncryptedPdfError(FileValidationError):
    pass


@dataclass(frozen=True)
class ValidatedPdf:
    file_hash: str
    page_count: int
    file_size: int


def generate_storage_key(now: datetime | None = None) -> str:
    """Server-generated storage path: notes/<year>/<month>/<64-hex>.pdf.

    The original filename is metadata only (vision.txt §8); this key is what
    storage sees, so user input can never influence the filesystem path.
    """
    now = now or datetime.now(timezone.utc)
    return f"notes/{now:%Y}/{now:%m}/{secrets.token_hex(32)}.pdf"


def validate_pdf(data: BinaryIO) -> tuple[ValidatedPdf, SpooledTemporaryFile]:
    """Run the full validation pipeline and return (result, positioned file).

    The returned spooled file holds the exact uploaded bytes with the cursor
    at position 0, ready for storage.save(). The caller owns closing it.
    """
    hasher = hashlib.sha256()
    spool: SpooledTemporaryFile = SpooledTemporaryFile(
        max_size=_SPOOL_THRESHOLD_BYTES, dir=settings.STORAGE_DIR
    )
    total = 0

    try:
        while chunk := data.read(_READ_CHUNK_BYTES):
            total += len(chunk)
            if total > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise FileTooLargeError(
                    f"file exceeds the {settings.MAX_FILE_SIZE_MB} MB limit"
                )
            hasher.update(chunk)
            spool.write(chunk)
    except BaseException:
        spool.close()
        raise

    # --- Magic bytes: reject before the parser ever sees the file -----------
    spool.seek(0)
    if spool.read(len(PDF_MAGIC)) != PDF_MAGIC:
        spool.close()
        raise NotAPdfError("file is not a PDF document")

    # --- Parse, page count, encryption ---------------------------------------
    try:
        spool.seek(0)
        reader = PdfReader(spool)
        if reader.is_encrypted:
            raise EncryptedPdfError("password-protected PDFs are not supported")
        page_count = len(reader.pages)
    except EncryptedPdfError:
        spool.close()
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        spool.close()
        raise InvalidPdfError("file could not be parsed as a PDF") from exc

    if page_count < settings.MIN_PAGE_COUNT:
        spool.close()
        raise PageCountError(f"PDF has fewer than {settings.MIN_PAGE_COUNT} page(s)")
    if page_count > settings.MAX_PAGE_COUNT:
        spool.close()
        raise PageCountError(f"PDF exceeds the {settings.MAX_PAGE_COUNT}-page limit")

    # PdfReader leaves the cursor anywhere in the stream; reposition to 0 so
    # the caller can hand the spool straight to storage.save().
    spool.seek(0)
    return (
        ValidatedPdf(
            file_hash=hasher.hexdigest(),
            page_count=page_count,
            file_size=total,
        ),
        spool,
    )
