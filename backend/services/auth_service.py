"""Authentication business logic (vision.txt §7: services).

Routes call into this module; HTTP concerns stay out of it.

Register is transactional: the User and their Wallet (balance 0) are created
together, so an account can never exist without a wallet.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import User, UserRole, Wallet
from backend.utils import auth_helpers


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def _normalize_email(email: str) -> str:
    """Canonical form for uniqueness lookups only; the user's email is
    stored exactly as provided and always returned from the API.

    Anti-multi-account policy:
    * plus-addressing (user+tag@) is stripped for ALL domains — the classic
      alias-abuse vector; two aliases must not create two accounts;
    * dots are stripped only for gmail/googlemail, where they are meaningless;
      elsewhere dots can be significant.
    """
    local, _, domain = email.partition("@")
    local = local.lower()
    domain = domain.lower()
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
    return f"{local}@{domain}"


def register_user(db: Session, *, email: str, name: str, password: str) -> User:
    """Create a user and their wallet in one transaction."""
    normalized = _normalize_email(email)
    existing = db.scalar(select(User).where(User.normalized_email == normalized))
    if existing is not None:
        raise EmailAlreadyRegisteredError()

    user = User(
        email=email,
        normalized_email=normalized,
        name=name,
        password_hash=auth_helpers.hash_password(password),
        role=UserRole.STUDENT,  # role is decided server-side only
        is_active=True,
        wallet=Wallet(balance=0),  # same transaction: no user without a wallet
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Race-safe dedup: two concurrent registrations of the same email —
        # only one commit wins; the loser gets a clean 409, never a 500.
        db.rollback()
        raise EmailAlreadyRegisteredError() from None
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Verify credentials. Raises InvalidCredentialsError on any failure.

    A bcrypt hash is computed even when the email is unknown so that the
    response time for unknown emails matches the response time for wrong
    passwords (user enumeration resistance).
    """
    normalized = _normalize_email(email)
    user = db.scalar(select(User).where(User.normalized_email == normalized))
    if user is None:
        auth_helpers.hash_password(password)  # burn comparable CPU time
        raise InvalidCredentialsError()
    if not auth_helpers.verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InvalidCredentialsError()
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    """Create an (access, refresh) token pair for a user."""
    return auth_helpers.create_access_token(user.id), auth_helpers.create_refresh_token(user.id)


def rotate_refresh_token(db: Session, *, refresh_token: str) -> User:
    """Validate a refresh token and return its user (for re-issuing tokens)."""
    try:
        claims = auth_helpers.decode_token(
            refresh_token, expected_type=auth_helpers.REFRESH_TOKEN_TYPE
        )
        user_id = int(claims["sub"])
    except (auth_helpers.InvalidTokenError, KeyError, ValueError):
        raise InvalidRefreshTokenError() from None

    user = db.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or auth_helpers.token_revoked(claims, user.token_invalid_before)
    ):
        raise InvalidRefreshTokenError()
    return user


def logout_user(db: Session, *, refresh_token: str) -> None:
    """Invalidate all previously issued tokens by bumping the revocation point.

    Idempotent: an already-revoked token is a no-op (200 either way).
    Malformed/expired tokens are also no-ops, never errors.
    """
    try:
        claims = auth_helpers.decode_token(
            refresh_token, expected_type=auth_helpers.REFRESH_TOKEN_TYPE
        )
        user_id = int(claims["sub"])
    except (auth_helpers.InvalidTokenError, KeyError, ValueError):
        return

    user = db.get(User, user_id)
    if user is not None and not auth_helpers.token_revoked(claims, user.token_invalid_before):
        # JWT `iat` has whole-second granularity: floor the revocation point to
        # the current second so every token issued up to and including this
        # second fails the `iat <= token_invalid_before` check (fail closed).
        user.token_invalid_before = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
