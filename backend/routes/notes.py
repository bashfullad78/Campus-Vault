"""Note endpoints (vision.txt V1: Notes).

Routes parse requests, authenticate, delegate to note_service, and map
service errors to the PRD's HTTP codes (§13):
  401 missing/invalid auth · 404 unknown resource · 409 duplicate/insufficient
  413 oversized · 422 invalid input · 429 rate limited.
"""

from typing import Annotated, BinaryIO

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import User
from backend.schemas.note import NoteListOut, NoteOut
from backend.services import coin_service, note_service
from backend.storage import StorageError, get_storage
from backend.utils.dependencies import get_current_user
from backend.utils.file_helpers import FileTooLargeError, FileValidationError
from backend.utils.rate_limit import rate_limit

router = APIRouter(prefix="/notes", tags=["notes"])

_upload_limit = rate_limit(settings.UPLOAD_RATE_LIMIT, scope="upload")

# Multipart fields cannot reuse the NoteCreate model directly, so the same
# constraints are enforced via Form validation here.
_TITLE_MAX = 255
_CHAPTER_MAX = 255


def _validation_http_error(exc: FileValidationError) -> HTTPException:
    if isinstance(exc, FileTooLargeError):
        return HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def upload_note(
    subject_id: Annotated[int, Form(gt=0)],
    title: Annotated[str, Form(min_length=1, max_length=_TITLE_MAX)],
    file: Annotated[UploadFile, File(description="PDF document")],
    chapter: Annotated[str | None, Form(max_length=_CHAPTER_MAX)] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_upload_limit),
) -> NoteOut:
    """Upload a PDF note. Fully validated server-side; duplicates → 409."""
    if file.content_type and file.content_type != "application/pdf":
        # Advisory only: this header is client-controlled. The real checks are
        # magic bytes, parsing, and page count inside the validation pipeline.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Only PDF files are accepted"
        )
    try:
        note, _rewarded = note_service.create_note(
            db,
            get_storage(),
            owner_id=current_user.id,
            subject_id=subject_id,
            title=title,
            chapter=chapter,
            original_filename=file.filename or "unknown.pdf",
            upload_fileobj=file.file,
        )
    except FileTooLargeError as exc:
        raise _validation_http_error(exc)
    except FileValidationError as exc:
        raise _validation_http_error(exc)
    except note_service.SubjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    except note_service.DuplicateNoteError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An identical file has already been uploaded"
        )
    except StorageError:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to store file"
        )
    return NoteOut.model_validate(note)


@router.get("", response_model=NoteListOut)
def list_notes(
    subject_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListOut:
    """List ACTIVE notes, optionally filtered by subject. Requires auth."""
    notes, total = note_service.list_notes(
        db, subject_id=subject_id, limit=limit, offset=offset
    )
    return NoteListOut(notes=[NoteOut.model_validate(n) for n in notes], total=total)


@router.get("/my", response_model=NoteListOut)
def list_my_notes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListOut:
    """List the authenticated user's own ACTIVE notes."""
    notes, total = note_service.list_my_notes(
        db, current_user.id, limit=limit, offset=offset
    )
    return NoteListOut(notes=[NoteOut.model_validate(n) for n in notes], total=total)


@router.get("/{note_id}", response_model=NoteOut)
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteOut:
    try:
        note = note_service.get_active_note(db, note_id)
    except note_service.NoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return NoteOut.model_validate(note)


@router.get("/{note_id}/download")
def download_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download a note. Non-owners pay DOWNLOAD_COST coins atomically."""
    try:
        note, fileobj = note_service.download_note(
            db, get_storage(), user_id=current_user.id, note_id=note_id
        )
    except note_service.NoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    except coin_service.InsufficientCoinsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Insufficient coins to download this note"
        )
    except StorageError:
        # Coin charge already rolled back inside the service.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stored file is unavailable")

    # original_filename is metadata validated at upload time; it is quoted to
    # neutralize header injection via CRLF (FastAPI/HTTP layer would reject
    # raw newlines anyway).
    safe_name = note.original_filename.replace('"', "'")
    return StreamingResponse(
        fileobj,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.delete("/{note_id}", status_code=status.HTTP_200_OK)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        note_service.delete_note(db, get_storage(), user_id=current_user.id, note_id=note_id)
    except note_service.NoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    except note_service.NoteNotOwnedError:
        # §13: authenticated but not authorized → 403.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this note")
    except StorageError:
        pass  # DB already updated; an orphaned file is an ops/log concern
    return {"detail": "Note deleted"}
