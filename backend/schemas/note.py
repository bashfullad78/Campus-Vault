"""Pydantic schemas for the Note resource.

NoteOut deliberately excludes `storage_key` and `file_hash`: internal storage
locations must never leave the API (vision.txt §6: schemas define exactly what
data may leave the API; §11: storage paths are not exposed).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.note import NoteStatus
from backend.schemas.subject import SubjectOut


class NoteCreate(BaseModel):
    """Payload semantics for uploads. In multipart requests FastAPI applies
    the same constraints to the individual Form fields."""

    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    chapter: str | None = Field(default=None, max_length=255)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    subject_id: int
    title: str
    chapter: str | None
    original_filename: str
    file_size: int
    page_count: int
    status: NoteStatus
    subject: SubjectOut
    created_at: datetime
    updated_at: datetime


class NoteListOut(BaseModel):
    notes: list[NoteOut]
    total: int
