"""initial schema: users, wallets, wallet_transactions, subjects, notes, ratings

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-06

Creates the full V1 schema directly from the SQLAlchemy model metadata so the
migration can never drift from the models at authoring time. Downgrade drops
all tables and the PostgreSQL enum types.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL enum type names created by the models' Enum(...) definitions.
PG_ENUM_TYPES = ("userrole", "transactiontype", "referencetype", "notestatus")


def upgrade() -> None:
    from backend.database import Base
    import backend.models  # noqa: F401  -- registers all models on Base.metadata

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from backend.database import Base
    import backend.models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind())

    # drop_all removes tables; enum types are dropped explicitly for safety.
    type_list = ", ".join(PG_ENUM_TYPES)
    op.execute(f"DROP TYPE IF EXISTS {type_list}")
