"""Shared fixtures for the V1 test suite (vision.txt §14).

These tests run against the configured dev database (the DB user has no
CREATEDB privilege for a disposable database). Isolation strategy:
* all test accounts are namespaced under v1test-<tag>@example.com;
* leftover v1test users are wiped at session start (crash recovery) and after
  each test (cascade removes wallets/notes/ratings/ledger rows);
* uploaded files live under storage/notes (gitignored) and are swept at
  session boundaries;
* the in-process rate limiter is disabled so tests sharing one client IP
  never interfere with each other.
"""

import io
import shutil
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.config import settings
from backend.database import SessionLocal
from backend.main import app
from backend.models import Subject, User

TEST_EMAIL_TEMPLATE = "v1test-{tag}@example.com"
TEST_PASSWORD = "password123"


@pytest.fixture(scope="session", autouse=True)
def _session_isolation() -> Any:
    """Disable rate limiting and sweep leftovers before/after the session."""
    old = settings.RATE_LIMIT_ENABLED
    settings.RATE_LIMIT_ENABLED = False

    db = SessionLocal()
    for u in db.query(User).filter(User.email.like("v1test-%")).all():
        db.delete(u)
    db.commit()
    db.close()

    shutil.rmtree("storage/notes", ignore_errors=True)
    yield
    settings.RATE_LIMIT_ENABLED = old
    shutil.rmtree("storage/notes", ignore_errors=True)


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def user_factory(client: TestClient) -> Iterator[Callable[[str], dict]]:
    """Register + login a namespaced test user; delete it on teardown.

    Returns {"headers": auth headers, "token": access token, "user": profile}.
    """
    created: list[str] = []

    def _make(tag: str) -> dict:
        email = TEST_EMAIL_TEMPLATE.format(tag=tag)
        r = client.post(
            "/auth/register",
            json={"email": email, "name": f"User {tag}", "password": TEST_PASSWORD},
        )
        assert r.status_code == 201, r.text
        r_login = client.post(
            "/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert r_login.status_code == 200, r_login.text
        created.append(email)
        return {
            "headers": {"Authorization": f"Bearer {r_login.json()['access_token']}"},
            "token": r_login.json()["access_token"],
            "user": r.json(),
        }

    yield _make

    db = SessionLocal()
    for email in created:
        u = db.query(User).filter(User.email == email).first()
        if u is not None:
            db.delete(u)
    db.commit()
    db.close()


@pytest.fixture(scope="session")
def subject_id() -> int:
    db = SessionLocal()
    row = db.query(Subject.id).filter(Subject.semester == 5).first()
    db.close()
    assert row is not None, "subject seed missing — run alembic upgrade head"
    return row[0]


@pytest.fixture
def make_pdf() -> Callable[..., io.BytesIO]:
    """Build a distinct valid PDF per tag (metadata differs → hash differs)."""

    def _make(tag: str = "") -> io.BytesIO:
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        if tag:
            writer.add_metadata({"/Title": tag})
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return buf

    return _make


@pytest.fixture
def upload(
    client: TestClient,
    make_pdf: Callable[..., io.BytesIO],
    subject_id: int,
) -> Callable[..., Any]:
    """POST a fresh PDF to /notes as the given auth headers."""

    def _upload(headers: dict, tag: str, sid: int | None = None) -> Any:
        return client.post(
            "/notes",
            headers=headers,
            data={"subject_id": str(sid or subject_id), "title": f"Note {tag}", "chapter": "Ch 1"},
            files={"file": (f"{tag}.pdf", make_pdf(tag), "application/pdf")},
        )

    return _upload
