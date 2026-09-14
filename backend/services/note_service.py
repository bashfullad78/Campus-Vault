"""Note service: upload pipeline, retrieval, download, deletion (vision.txt V1: Notes).

Upload order (vision.txt V1: File Validation + Transaction Safety):
  auth (route) → validate PDF → dedup pre-check → storage.save →
  INSERT note (flush) → coin reward (same transaction) → commit.
The partial unique index on active-note hashes is the race-safe backstop:
if two identical files upload concurrently, the second commit fails with an
IntegrityError and its stored file is removed.

Download charges coins BEFORE streaming, but commits only after the stored
file has been opened successfully — a user never pays for an unavailable file.
Self-downloads are always free (vision.txt V1 decision).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Note, NoteStatus, Subject
from backend.services import coin_service
from backend.services.coin_service import InsufficientCoinsError  # noqa: F401 (re-exported)
from backend.storage import StorageBackend, StorageError
from backend.utils.file_helpers import (
    ValidatedPdf,
    generate_storage_key,
    validate_pdf,
)
from typing import BinaryIO


class NoteNotFoundError(Exception):
    pass


class NoteNotOwnedError(Exception):
    pass


class DuplicateNoteError(Exception):
    pass


class SubjectNotFoundError(Exception):
    pass


def create_note(
    db: Session,
    storage: StorageBackend,
    *,
    owner_id: int,
    subject_id: int,
    title: str,
    chapter: str | None,
    original_filename: str,
    upload_fileobj: BinaryIO,
) -> tuple[Note, bool]:
    """Validate, store, and persist an uploaded PDF. Returns (note, rewarded).

    `rewarded` is False when the daily upload-reward cap was already reached;
    the note is still created (vision.txt V1 decision).
    """
    # --- Subject must exist (client-supplied id is never trusted to be valid) ---
    if db.get(Subject, subject_id) is None:
        raise SubjectNotFoundError(f"subject {subject_id} does not exist")

    # --- Full validation pipeline: size → magic → parse → pages → hash -------
    validated: ValidatedPdf
    validated, spool = validate_pdf(upload_fileobj)

    # --- Dedup pre-check against ACTIVE notes (global, not per-user) ---------
    dup = db.scalar(
        select(Note.id).where(
            Note.file_hash == validated.file_hash,
            Note.status == NoteStatus.ACTIVE,
        )
    )
    if dup is not None:
        spool.close()
        raise DuplicateNoteError("an identical file has already been uploaded")

    # --- Storage: server-generated key only -----------------------------------
    storage_key = generate_storage_key()
    try:
        storage.save(storage_key, spool)
    finally:
        spool.close()

    note = Note(
        owner_id=owner_id,
        subject_id=subject_id,
        title=title.strip()[:255] or "Untitled",
        chapter=(chapter.strip()[:255] or None) if chapter else None,
        # Original filename is metadata only, bounded to the column size.
        original_filename=(original_filename or "unknown.pdf")[:255],
        storage_key=storage_key,
        file_hash=validated.file_hash,
        file_size=validated.file_size,
        page_count=validated.page_count,
        status=NoteStatus.ACTIVE,
    )
    db.add(note)
    try:
        db.flush()  # assigns note.id for the reward's reference_id
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise

    rewarded = coin_service.reward_user(db, owner_id, reference_id=note.id)

    try:
        db.commit()
    except Exception:
        # Includes the IntegrityError from a concurrent duplicate losing the
        # partial-unique race: remove the just-stored file, leave no trace.
        db.rollback()
        storage.delete(storage_key)
        raise DuplicateNoteError("an identical file has already been uploaded") from None
    db.refresh(note)
    return note, rewarded


def get_active_note(db: Session, note_id: int) -> Note:
    """Fetch an ACTIVE note by id; deleted/missing notes are indistinguishable."""
    note = db.get(Note, note_id)
    if note is None or note.status != NoteStatus.ACTIVE:
        raise NoteNotFoundError(f"note {note_id} not found")
    return note


def list_notes(
    db: Session,
    *,
    subject_id: int | None = None,
    owner_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Note], int]:
    """Public ACTIVE-note listing with optional subject/owner filters."""
    query = select(Note).where(Note.status == NoteStatus.ACTIVE)
    count_query = select(func.count()).select_from(Note).where(Note.status == NoteStatus.ACTIVE)
    if subject_id is not None:
        query = query.where(Note.subject_id == subject_id)
        count_query = count_query.where(Note.subject_id == subject_id)
    if owner_id is not None:
        query = query.where(Note.owner_id == owner_id)
        count_query = count_query.where(Note.owner_id == owner_id)
    notes = list(
        db.execute(
            query.order_by(Note.created_at.desc(), Note.id.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    total = db.execute(count_query).scalar_one()
    return notes, total


def list_my_notes(db: Session, user_id: int, *, limit: int, offset: int) -> tuple[list[Note], int]:
    """The authenticated user's own ACTIVE notes — owner filter is server-side."""
    return list_notes(db, owner_id=user_id, limit=limit, offset=offset)


def download_note(
    db: Session, storage: StorageBackend, *, user_id: int, note_id: int
) -> tuple[Note, BinaryIO]:
    """Authorize, charge coins (unless owner), open the file, commit.

    Returns the note and an open binary stream for the route to stream.
    The coin charge and the successful file open share one transaction, so a
    missing file can never be paid for; conversely a successful charge always
    corresponds to a retrievable file.
    """
    note = get_active_note(db, note_id)
    if note.owner_id != user_id:
        coin_service.charge_download(db, user_id, note_id=note.id)
    try:
        fileobj = storage.open(note.storage_key)
    except StorageError:
        db.rollback()  # releases the charge — user is not billed
        raise
    db.commit()  # coins change hands only now
    return note, fileobj


def delete_note(db: Session, storage: StorageBackend, *, user_id: int, note_id: int) -> None:
    """Soft-delete an owned note and remove its file.

    Per the V1 decision, the hash is cleared so the file becomes uploadable
    again. Ownership is checked server-side; knowing the id is not enough.
    """
    note = get_active_note(db, note_id)
    if note.owner_id != user_id:
        raise NoteNotOwnedError("you do not own this note")

    note.status = NoteStatus.DELETED
    note.file_hash = None
    db.commit()

    # DB first, file second: a failed file removal leaves an orphan on disk
    # (visible in logs) but never a DB row pointing at a missing file.
    storage.delete(note.storage_key)
