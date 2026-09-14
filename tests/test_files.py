"""File validation tests (vision.txt §14: File tests)."""

import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _encrypted_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")  # owner password set → is_encrypted
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_valid_pdf_accepted(client, user_factory, upload) -> None:
    auth = user_factory("file-ok")
    r = upload(auth["headers"], "OK1")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["page_count"] == 1
    assert body["file_size"] > 0
    assert body["status"] == "ACTIVE"


def test_exe_renamed_to_pdf_rejected(client, user_factory, subject_id) -> None:
    """A shell script with a .pdf name must never pass (magic bytes)."""
    auth = user_factory("file-fake")
    r = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": str(subject_id), "title": "Fake"},
        files={"file": ("innocent.pdf", io.BytesIO(b"#!/bin/sh\nrm -rf /"), "application/pdf")},
    )
    assert r.status_code == 422


def test_corrupt_truncated_pdf_rejected(client, user_factory, subject_id) -> None:
    auth = user_factory("file-corrupt")
    truncated = _blank_pdf_bytes()[:40]
    r = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": str(subject_id), "title": "Corrupt"},
        files={"file": ("broken.pdf", io.BytesIO(truncated), "application/pdf")},
    )
    assert r.status_code == 422


def test_encrypted_pdf_rejected(client, user_factory, subject_id) -> None:
    auth = user_factory("file-encrypted")
    r = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": str(subject_id), "title": "Encrypted"},
        files={"file": ("locked.pdf", io.BytesIO(_encrypted_pdf_bytes()), "application/pdf")},
    )
    assert r.status_code == 422


def test_oversized_pdf_rejected_413(client, user_factory, subject_id) -> None:
    """> MAX_FILE_SIZE_MB must map to 413 (vision.txt §13)."""
    auth = user_factory("file-big")
    big = b"%PDF-1.4\n" + b"\x00" * (26 * 1024 * 1024)  # 26 MB > 25 MB limit
    r = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": str(subject_id), "title": "Big"},
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
    )
    assert r.status_code == 413


def test_duplicate_pdf_rejected_globally(client, user_factory, upload, make_pdf) -> None:
    """Same file bytes from a *different* user → 409 (global dedup)."""
    owner = user_factory("dup-owner")
    other = user_factory("dup-other")
    first = upload(owner["headers"], "DUP")
    assert first.status_code == 201
    # Identical bytes (make_pdf is deterministic per tag), different user.
    r = client.post(
        "/notes",
        headers=other["headers"],
        data={"subject_id": first.json()["subject_id"], "title": "Note DUP again"},
        files={"file": ("DUP.pdf", make_pdf("DUP"), "application/pdf")},
    )
    assert r.status_code == 409, r.text


def test_storage_key_never_exposed_in_responses(client, user_factory, upload) -> None:
    """Internal storage path and hash must not leak (vision.txt §6)."""
    auth = user_factory("leak")
    r = upload(auth["headers"], "LEAK")
    assert r.status_code == 201
    body_text = repr(r.json())
    assert "storage_key" not in body_text
    assert "file_hash" not in body_text
    detail = client.get(f"/notes/{r.json()['id']}", headers=auth["headers"]).json()
    assert "storage_key" not in repr(detail)
