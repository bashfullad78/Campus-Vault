"""Subject catalog endpoints (vision.txt V1 decision: read-only subjects).

The catalog is seeded by migration 0002; there is no write path in V1.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Subject
from backend.schemas.subject import SubjectOut
from backend.utils.dependencies import get_current_user

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
def list_subjects(
    semester: int | None = Query(default=None, ge=1, le=10),
    db: Session = Depends(get_db),
    _: None = Depends(get_current_user),
) -> list[SubjectOut]:
    """List the subject catalog, optionally filtered by semester."""
    query = select(Subject).order_by(Subject.semester, Subject.code)
    if semester is not None:
        query = query.where(Subject.semester == semester)
    return list(db.execute(query).scalars().all())
