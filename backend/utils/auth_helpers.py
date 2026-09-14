"""Password hashing and JWT creation/verification (vision.txt §7: utils).

Tokens carry a `type` claim so a refresh token can never stand in for an
access token, and an `iat` claim compared against the user's revocation
timestamp so logout can invalidate previously issued tokens without Redis.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from backend.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class InvalidTokenError(Exception):
    """Token is malformed, expired, wrong type, or otherwise untrusted."""


# --- Passwords -------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # Stored hash in unexpected format -> treat as mismatch, never crash.
        return False


# --- Tokens ----------------------------------------------------------------


def _create_token(user_id: int, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id, ACCESS_TOKEN_TYPE, timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id, REFRESH_TOKEN_TYPE, timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Decode and validate signature, expiry, and token type.

    Raises InvalidTokenError for anything that should map to a 401.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],  # pinned: "none" can never pass
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("wrong token type")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise InvalidTokenError("malformed subject")
    if "iat" not in payload:
        raise InvalidTokenError("missing iat")
    return payload


def token_revoked(claims: dict, token_invalid_before: datetime | None) -> bool:
    """True when the token was issued at/before the user's revocation point.

    Issued-at has second granularity, so `<=` is used: tokens issued in the
    same second as a logout are treated as revoked (fail closed).
    """
    if token_invalid_before is None:
        return False
    issued_at = datetime.fromtimestamp(int(claims["iat"]), tz=timezone.utc)
    return issued_at <= token_invalid_before
