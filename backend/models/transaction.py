"""WalletTransaction model: append-only coin ledger (vision.txt §8)."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class TransactionType(str, enum.Enum):
    UPLOAD_REWARD = "UPLOAD_REWARD"
    NOTE_DOWNLOAD = "NOTE_DOWNLOAD"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"


class ReferenceType(str, enum.Enum):
    NOTE = "NOTE"
    ADMIN = "ADMIN"


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Positive = credit, negative = debit. Signed at insert time; never updated.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transactiontype", native_enum=True), nullable=False
    )
    reference_type: Mapped[ReferenceType | None] = mapped_column(
        Enum(ReferenceType, name="referencetype", native_enum=True), nullable=True
    )
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Serves the daily reward-cap query: count UPLOAD_REWARD for a wallet today.
        Index("ix_wallet_tx_wallet_type_created", "wallet_id", "transaction_type", "created_at"),
    )

    wallet = relationship("Wallet", back_populates="transactions")
