"""Note model: uploaded academic PDFs (vision.txt §8)."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class NoteStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Original filename is metadata only; storage path is server-generated.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    # Dedup: hash is cleared on deletion so the file becomes uploadable again
    # (V1 decision: dedup scoped to active notes).
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[NoteStatus] = mapped_column(
        Enum(NoteStatus, name="notestatus", native_enum=True),
        default=NoteStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("file_size > 0", name="file_size_positive"),
        CheckConstraint("page_count >= 1", name="page_count_min"),
        # Partial unique index: duplicate detection considers ACTIVE notes only.
        Index(
            "uq_notes_file_hash_active",
            "file_hash",
            unique=True,
            postgresql_where=text("status = 'ACTIVE' AND file_hash IS NOT NULL"),
        ),
        Index("ix_notes_owner_status", "owner_id", "status"),
    )

    owner = relationship("User", back_populates="notes")
    subject = relationship("Subject", back_populates="notes")
    ratings = relationship("Rating", back_populates="note")
