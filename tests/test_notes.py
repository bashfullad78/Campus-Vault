"""Note ownership, isolation, and CRUD tests (vision.txt §12–§14).

Core property under test: knowing a resource id never grants access to it.
"""

from fastapi.testclient import TestClient


def test_upload_lists_and_details(client, user_factory, upload) -> None:
    auth = user_factory("crud")
    r = upload(auth["headers"], "CRUD1")
    assert r.status_code == 201, r.text
    note_id = r.json()["id"]

    listed = client.get("/notes", headers=auth["headers"]).json()
    assert listed["total"] >= 1 and any(n["id"] == note_id for n in listed["notes"])

    mine = client.get("/notes/my", headers=auth["headers"]).json()
    assert mine["total"] == 1 and mine["notes"][0]["id"] == note_id

    detail = client.get(f"/notes/{note_id}", headers=auth["headers"])
    assert detail.status_code == 200
    assert detail.json()["title"] == "Note CRUD1"


def test_subject_filter(client, user_factory, upload, subject_id) -> None:
    auth = user_factory("filter")
    upload(auth["headers"], "F1", sid=subject_id)
    r = client.get(f"/notes?subject_id={subject_id}", headers=auth["headers"])
    assert r.status_code == 200
    assert all(n["subject_id"] == subject_id for n in r.json()["notes"])


def test_deleted_note_is_hidden_everywhere(client, user_factory, upload) -> None:
    """A soft-deleted note must vanish from list, detail, and download."""
    auth = user_factory("softdel")
    note_id = upload(auth["headers"], "GONE").json()["id"]
    assert client.delete(f"/notes/{note_id}", headers=auth["headers"]).status_code == 200

    assert client.get(f"/notes/{note_id}", headers=auth["headers"]).status_code == 404
    listed = client.get("/notes/my", headers=auth["headers"]).json()
    assert all(n["id"] != note_id for n in listed["notes"])
    assert client.get(f"/notes/{note_id}/download", headers=auth["headers"]).status_code == 404


def test_idor_user_a_cannot_read_or_delete_user_b_note(client, user_factory, upload) -> None:
    """The §14 authorization matrix: A↔B read/delete must be denied."""
    a = user_factory("idor-a")
    b = user_factory("idor-b")
    note_id = upload(a["headers"], "AB").json()["id"]

    # B reads A's note: detail is public-to-authenticated users, but B must not
    # delete it. (V1 has no note-edit endpoint; delete is the mutation.)
    assert client.delete(f"/notes/{note_id}", headers=b["headers"]).status_code == 403
    # ...and the note must still exist afterwards.
    assert client.get(f"/notes/{note_id}", headers=a["headers"]).status_code == 200

    # Unknown ids are 404 for everyone.
    assert client.get("/notes/99999999", headers=b["headers"]).status_code == 404
    assert client.delete("/notes/99999999", headers=b["headers"]).status_code == 404


def test_deleted_note_hash_becomes_reuploadable(client, user_factory, upload, make_pdf) -> None:
    """V1 decision: deleting a note clears its hash → same file OK again."""
    auth = user_factory("rehash")
    first = upload(auth["headers"], "RE1")
    assert first.status_code == 201
    note_id = first.json()["id"]

    dup = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": first.json()["subject_id"], "title": "RE1 again"},
        files={"file": ("RE1.pdf", make_pdf("RE1"), "application/pdf")},
    )
    assert dup.status_code == 409  # still active → dedup applies

    assert client.delete(f"/notes/{note_id}", headers=auth["headers"]).status_code == 200

    again = client.post(
        "/notes",
        headers=auth["headers"],
        data={"subject_id": first.json()["subject_id"], "title": "RE1 re-uploaded"},
        files={"file": ("RE1.pdf", make_pdf("RE1"), "application/pdf")},
    )
    assert again.status_code == 201, again.text


def test_download_self_free_other_paid(client, user_factory, upload) -> None:
    a = user_factory("dl-a")
    b = user_factory("dl-b")
    note_id = upload(a["headers"], "DL").json()["id"]

    # Owner downloads free.
    r = client.get(f"/notes/{note_id}/download", headers=a["headers"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert client.get("/coins/balance", headers=a["headers"]).json()["balance"] == 10

    # Fund B with an upload reward so they can actually pay.
    upload(b["headers"], "DL-B-SEED")
    assert client.get("/coins/balance", headers=b["headers"]).json()["balance"] == 10

    # Non-owner pays 5.
    r = client.get(f"/notes/{note_id}/download", headers=b["headers"])
    assert r.status_code == 200
    assert client.get("/coins/balance", headers=b["headers"]).json()["balance"] == 5


def test_deleted_owner_cannot_redownload(client, user_factory, upload) -> None:
    auth = user_factory("dl-del")
    note_id = upload(auth["headers"], "DLG").json()["id"]
    client.delete(f"/notes/{note_id}", headers=auth["headers"])
    assert client.get(f"/notes/{note_id}/download", headers=auth["headers"]).status_code == 404


def test_list_requires_authentication(client) -> None:
    assert client.get("/notes").status_code == 401
    assert client.get("/notes/my").status_code == 401
    assert client.get("/subjects").status_code == 401
