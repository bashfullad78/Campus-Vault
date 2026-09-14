"""Coin service: the only code allowed to move coins (vision.txt V1: Coin System).

Invariants enforced here:
* Server-side balance calculations only — the client never submits amounts.
* Atomicity: balance update and ledger insert share one transaction, and the
  wallet row is locked (SELECT ... FOR UPDATE) so concurrent spends serialize.
  The `balance >= 0` CHECK constraint (wallet model) is the final backstop:
  the balance can never go negative even under a lock-acquisition race.
* Append-only ledger: rows are inserted, never updated or deleted.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.models import TransactionType, ReferenceType, User, Wallet, WalletTransaction
from backend.config import settings


class WalletNotFoundError(Exception):
    pass


class InsufficientCoinsError(Exception):
    pass


def _lock_wallet(db: Session, user_id: int) -> Wallet:
    """Fetch the user's wallet with a row lock held until commit/rollback.

    `with_for_update()` serializes concurrent coin mutations for the same
    user; other transactions touching this row block until this one ends.
    """
    wallet = db.execute(
        select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if wallet is None:
        raise WalletNotFoundError(f"no wallet for user {user_id}")
    return wallet


def _insert_transaction(
    db: Session,
    *,
    wallet: Wallet,
    amount: int,
    transaction_type: TransactionType,
    reference_type: ReferenceType | None = None,
    reference_id: int | None = None,
) -> WalletTransaction:
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,  # signed: positive credits, negative debits
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(tx)
    # The app runs with autoflush=False, so the ledger row must be flushed
    # explicitly: the daily-reward-cap COUNT in reward_user would otherwise
    # miss pending rows and over-reward within a single request.
    db.flush()
    return tx


def reward_user(db: Session, user_id: int, *, reference_id: int) -> bool:
    """Credit an upload reward, honoring the per-user daily cap.

    Runs inside the caller's transaction. Returns True when the reward was
    granted, False when the user already reached today's cap. The cap is
    counted from the ledger (per user, not per file), so duplicate hashes
    cannot be used to farm coins (vision.txt V1 decision).
    """
    wallet = _lock_wallet(db, user_id)
    day_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rewarded_today = db.scalar(
        select(func.count())
        .select_from(WalletTransaction)
        .where(
            WalletTransaction.wallet_id == wallet.id,
            WalletTransaction.transaction_type == TransactionType.UPLOAD_REWARD,
            WalletTransaction.created_at >= day_start,
        )
    )
    if rewarded_today >= settings.DAILY_REWARD_CAP:
        return False

    _insert_transaction(
        db,
        wallet=wallet,
        amount=settings.UPLOAD_REWARD,
        transaction_type=TransactionType.UPLOAD_REWARD,
        reference_type=ReferenceType.NOTE,
        reference_id=reference_id,
    )
    wallet.balance += settings.UPLOAD_REWARD
    return True


def charge_download(db: Session, user_id: int, *, note_id: int) -> None:
    """Debit the download cost, atomically (runs inside caller's transaction).

    Raises InsufficientCoinsError without touching the balance when the user
    cannot afford it — the state is checked and mutated under the same row
    lock, so concurrent spends of a nearly-empty wallet serialize correctly.
    """
    wallet = _lock_wallet(db, user_id)
    if wallet.balance < settings.DOWNLOAD_COST:
        raise InsufficientCoinsError(
            f"requires {settings.DOWNLOAD_COST} coins, balance is {wallet.balance}"
        )
    _insert_transaction(
        db,
        wallet=wallet,
        amount=-settings.DOWNLOAD_COST,
        transaction_type=TransactionType.NOTE_DOWNLOAD,
        reference_type=ReferenceType.NOTE,
        reference_id=note_id,
    )
    wallet.balance -= settings.DOWNLOAD_COST


def get_balance(db: Session, user_id: int) -> int:
    wallet = db.execute(select(Wallet).where(Wallet.user_id == user_id)).scalar_one_or_none()
    if wallet is None:
        raise WalletNotFoundError(f"no wallet for user {user_id}")
    return wallet.balance


def list_transactions(db: Session, user: User, *, limit: int, offset: int) -> list[WalletTransaction]:
    """The user's own ledger, newest first.

    Filters by wallet ownership server-side: passing another user's id can
    never widen the result (user isolation, vision.txt §V1 Security).
    """
    return list(
        db.execute(
            select(WalletTransaction)
            .join(Wallet, WalletTransaction.wallet_id == Wallet.id)
            .where(Wallet.user_id == user.id)
            .options(joinedload(WalletTransaction.wallet))
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .unique()
        .all()
    )
