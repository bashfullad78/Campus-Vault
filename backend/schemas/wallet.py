"""Pydantic schemas for wallets and the coin ledger."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.models.transaction import ReferenceType, TransactionType


class WalletBalanceOut(BaseModel):
    balance: int


class WalletTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    transaction_type: TransactionType
    reference_type: ReferenceType | None
    reference_id: int | None
    created_at: datetime
