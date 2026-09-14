"""Authentication tests (vision.txt §14: Authentication tests)."""

from fastapi.testclient import TestClient


def test_register_login_me_roundtrip(client: TestClient, user_factory) -> None:
    auth = user_factory("roundtrip")
    me = client.get("/auth/me", headers=auth["headers"])
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "v1test-roundtrip@example.com"
    assert "password_hash" not in body  # schemas must never leak the hash


def test_wrong_password_rejected(client: TestClient, user_factory) -> None:
    user_factory("wrongpw")
    r = client.post(
        "/auth/login",
        json={"email": "v1test-wrongpw@example.com", "password": "definitely-not-it"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_unknown_email_and_wrong_password_share_one_message(
    client: TestClient,
) -> None:
    """User-enumeration resistance: same 401 + same message for both cases."""
    r1 = client.post(
        "/auth/login",
        json={"email": "v1test-who-dis@example.com", "password": "whatever123"},
    )
    r2 = client.post(
        "/auth/login",
        json={"email": "v1test-who-dis@example.com", "password": "otherpass456"},
    )
    assert r1.status_code == 401 and r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"] == "Invalid email or password"


def test_missing_token_rejected(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_invalid_and_garbage_tokens_rejected(client: TestClient) -> None:
    for token in ("garbage", "a.b.c"):
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_expired_token_rejected(client: TestClient, user_factory) -> None:
    """A properly signed token with a past exp must fail with 401."""
    from datetime import datetime, timedelta, timezone

    import jwt

    from backend.config import settings

    auth = user_factory("expired")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(auth["user"]["id"]),
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),  # already expired
        "jti": "test-jti",
    }
    expired = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_refresh_token_cannot_authenticate_as_access_token(
    client: TestClient, user_factory
) -> None:
    """Type-claim confusion: a refresh token must never pass an access check."""
    auth = user_factory("tokentype")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {auth['token']}"})
    assert r.status_code == 200  # sanity: real access token works
    login = client.post(
        "/auth/login",
        json={"email": "v1test-tokentype@example.com", "password": "password123"},
    )
    refresh = login.json()["refresh_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401


def test_logout_revokes_previously_issued_tokens(client: TestClient, user_factory) -> None:
    auth = user_factory("logout")
    login = client.post(
        "/auth/login",
        json={"email": "v1test-logout@example.com", "password": "password123"},
    )
    access, refresh = login.json()["access_token"], login.json()["refresh_token"]
    r = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 200
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 401  # revoked via token_invalid_before


def test_deactivated_account_rejected(client: TestClient) -> None:
    """is_active=False must block login AND invalidate live tokens (403)."""
    from backend.database import SessionLocal
    from backend.models import User

    email = "v1test-deactivated@example.com"
    r = client.post(
        "/auth/register", json={"email": email, "name": "D", "password": "password123"}
    )
    assert r.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    db = SessionLocal()
    u = db.query(User).filter(User.email == email).one()
    u.is_active = False
    db.commit()
    db.close()

    assert client.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 403

    db = SessionLocal()
    u = db.query(User).filter(User.email == email).one()
    db.delete(u)
    db.commit()
    db.close()
