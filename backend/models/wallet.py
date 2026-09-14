"""Wallet model: one per user, holds the coin balance (vision.txt §8 + V1 decision)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # Coin balances are never negative; CHECK constraint backs this up.
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
        CheckConstraint("balance >= 0", name="balance_non_negative"),
    )

    user = relationship("User", back_populates="wallet")
    transactions = relationship(
        "WalletTransaction",
        back_populates="wallet",
        order_by="WalletTransaction.created_at",
        # The FK is ON DELETE CASCADE and wallet_id is NOT NULL, so the DB must
        # delete ledger rows itself; SQLAlchemy must not try to NULL them out
        # (which would violate the NOT NULL constraint) when a wallet is removed.
        passive_deletes=True,
    )
