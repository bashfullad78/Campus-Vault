"""seed initial subject catalog

Revision ID: 0002_seed_subjects
Revises: 0001_initial_schema
Create Date: 2026-09-06

V1 decision (vision.txt): admin endpoints are deferred to V3, so the initial
subject catalog is created by a versioned seed migration. Subjects are
read-only in V1. Edit the list below and re-generate a seed migration for a
new college catalog; this one is idempotent-safe on a fresh database only.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_subjects"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Placeholder catalog: adjust to the actual college curriculum before deploying.
SEED_SUBJECTS = [
    {"code": "CS101", "name": "Programming Fundamentals", "semester": 1},
    {"code": "MA101", "name": "Engineering Mathematics I", "semester": 1},
    {"code": "CS201", "name": "Data Structures", "semester": 3},
    {"code": "CS202", "name": "Discrete Mathematics", "semester": 3},
    {"code": "CS301", "name": "Database Management Systems", "semester": 5},
    {"code": "CS302", "name": "Operating Systems", "semester": 5},
    {"code": "CS303", "name": "Computer Networks", "semester": 5},
    {"code": "CS401", "name": "Software Engineering", "semester": 7},
    {"code": "CS402", "name": "Machine Learning", "semester": 7},
    {"code": "CS403", "name": "Computer Security", "semester": 7},
]


def upgrade() -> None:
    subjects = sa.table(
        "subjects",
        sa.column("name", sa.String),
        sa.column("semester", sa.Integer),
        sa.column("code", sa.String),
    )
    op.bulk_insert(subjects, SEED_SUBJECTS)


def downgrade() -> None:
    codes = ", ".join(f"'{s['code']}'" for s in SEED_SUBJECTS)
    op.execute(f"DELETE FROM subjects WHERE code IN ({codes})")
