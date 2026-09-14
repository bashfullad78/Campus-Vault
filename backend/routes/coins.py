"""Coin endpoints (vision.txt V1 decision: coin read endpoints).

Read-only: balances and ledger history for the authenticated user only.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas.wallet import WalletBalanceOut, WalletTransactionOut
from backend.services import coin_service
from backend.utils.dependencies import get_current_user

router = APIRouter(prefix="/coins", tags=["coins"])


@router.get("/balance", response_model=WalletBalanceOut)
def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WalletBalanceOut:
    """The authenticated user's current coin balance."""
    try:
        balance = coin_service.get_balance(db, current_user.id)
    except coin_service.WalletNotFoundError:
        # Should be impossible (register creates the wallet atomically), but
        # never leak another user's data by way of an error message.
        raise HTTPException(status_code=500, detail="Wallet missing for authenticated user")
    return WalletBalanceOut(balance=balance)


@router.get("/transactions", response_model=list[WalletTransactionOut])
def list_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WalletTransactionOut]:
    """The authenticated user's ledger, newest first."""
    txs = coin_service.list_transactions(
        db, current_user, limit=limit, offset=offset
    )
    return [WalletTransactionOut.model_validate(t) for t in txs]
