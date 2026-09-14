"""add auth columns: users.normalized_email, users.token_invalid_before

Revision ID: 0003_user_auth_columns
Revises: 0002_seed_subjects
Create Date: 2026-09-06

normalized_email is backfilled from existing emails (lowercased) so the
UNIQUE constraint can be applied safely on a populated database.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_auth_columns"
down_revision: Union[str, None] = "0002_seed_subjects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("normalized_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "token_invalid_before", sa.DateTime(timezone=True), nullable=True
        ),
    )
    # Lowercase backfill: adequate for the empty/pre-launch database; the
    # Gmail dot/plus canonicalization in auth_service applies to new rows.
    op.execute("UPDATE users SET normalized_email = lower(email) WHERE normalized_email IS NULL")
    op.alter_column("users", "normalized_email", nullable=False)
    op.create_index(
        "ix_users_normalized_email", "users", ["normalized_email"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_normalized_email", table_name="users")
    op.drop_column("users", "token_invalid_before")
    op.drop_column("users", "normalized_email")
