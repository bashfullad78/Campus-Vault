"""Storage backend tests: key-contract conformance, S3 roundtrip, route wiring.

The suite's DB tests run against the configured dev database; these storage
tests deliberately don't need one — the storage layer is a dumb byte store and
its contract is (key, bytes) in/out. Two layers are covered:

* S3Storage against an in-memory fake bucket (no network, no credentials):
  put/get/delete roundtrip, strict key rejection, missing-key mapping,
  error translation (only StorageError escapes), and delete() driving the
  fake to exactly one real miss (no blind multi-delete).
* The route wiring end-to-end: with the backend cache primed with the fake,
  a real upload → list → download → delete HTTP flow must roundtrip through
  S3 and a save failure must leave no orphaned file or coin reward.

Local backend key validation is also re-run here so the shared contract
cannot drift between backends.
"""

import threading
from typing import Any
from unittest import mock

import pytest
from botocore.exceptions import ClientError

import backend.storage as storage_module
from backend.storage import LocalStorage, StorageError
from backend.storage.s3 import S3Storage

# ---------------------------------------------------------------------------
# Fake S3 client/bucket: thread-safe, fault-injectable, strictly observed.
# ---------------------------------------------------------------------------


def _missing(code: str, op: str) -> ClientError:
    """What real botocore raises for a missing object (parsed from the 404)."""
    return ClientError({"Error": {"Code": code, "Message": "not found"}}, op)


class FakeS3Bucket:
    """In-memory stand-in for an S3 bucket, driven through the botocore API.

    Inject `errors` entries to make a method raise once: the value is either
    an exception instance (raised as-is) or a string (wrapped in KeyError, as
    botocore does for unparseable GET error bodies, i.e. the 404 path).
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.errors: dict[str, Any] = {}
        self.delete_misses: list[str] = []
        self._lock = threading.Lock()

    def _raise_configured(self, method: str) -> None:
        err = self.errors.pop(method, None)
        if err is None:
            return
        if isinstance(err, BaseException):
            raise err
        raise KeyError(err)

    # --- botocore client surface used by S3Storage --------------------------

    def put_object(self, Bucket: str, Key: str, Body: Any, **kwargs: Any) -> dict:
        with self._lock:
            self._raise_configured("put_object")
            data = Body.read() if hasattr(Body, "read") else Body
            assert isinstance(data, bytes), "Body must be bytes or a readable stream"
            self.objects[Key] = data
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict:
        with self._lock:
            self._raise_configured("get_object")
            try:
                data = self.objects[Key]
            except KeyError:
                raise _missing("NoSuchKey", "GetObject")  # real botocore 404 shape
        return {"Body": _FakeStreamingBody(data)}

    def head_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict:
        with self._lock:
            self._raise_configured("head_object")
            if Key not in self.objects:
                raise _missing("404", "HeadObject")  # HEAD: code from status line
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def delete_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict:
        with self._lock:
            self._raise_configured("delete_object")
            if Key in self.objects:
                del self.objects[Key]
            else:
                self.delete_misses.append(Key)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class _FakeStreamingBody:
    """Faithful stand-in for botocore's StreamingBody.

    Real StreamingBody semantics reproduced: read() with no amount returns all
    remaining bytes, read(n) returns at most n, and the object is an iterator
    (starlette's StreamingResponse iterates file-likes — real files and
    StreamingBody both support __next__).
    """

    def __init__(self, data: bytes, chunk_size: int = 64 * 1024) -> None:
        self._data = data
        self._chunk_size = chunk_size
        self._pos = 0
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        end = self._pos + amt if amt is not None else len(self._data)
        chunk = self._data[self._pos : end]
        self._pos += len(chunk)
        return chunk

    def __iter__(self) -> "_FakeStreamingBody":
        return self

    def __next__(self) -> bytes:
        chunk = self._data[self._pos : self._pos + self._chunk_size]
        if not chunk:
            raise StopIteration
        self._pos += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


def make_storage(bucket: FakeS3Bucket) -> S3Storage:
    """Build S3Storage whose botocore client IS the fake bucket."""
    with mock.patch("backend.storage.s3.boto3.client", return_value=bucket):
        return S3Storage(
            bucket="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret",
            endpoint_url="http://fake.local",
            region="auto",
        )


def _hex(i: int) -> str:
    return f"{i:064x}"


# ---------------------------------------------------------------------------
# Key contract: every backend enforces the identical strict pattern.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", ["local", "s3"])
def test_backends_share_key_contract(backend_name: str) -> None:
    backend: Any = (
        LocalStorage("./storage")
        if backend_name == "local"
        else make_storage(FakeS3Bucket())
    )
    with pytest.raises(StorageError):
        backend.save("../escape.pdf", b"x")
    with pytest.raises(StorageError):
        backend.open("notes/2026/13/deadbeef.pdf")  # month 13: impossible
    with pytest.raises(StorageError):
        backend.delete("not-notes/2026/09/" + _hex(1) + ".pdf")


# ---------------------------------------------------------------------------
# S3Storage behavior.
# ---------------------------------------------------------------------------


def test_s3_roundtrip_save_open_delete() -> None:
    bucket = FakeS3Bucket()
    storage = make_storage(bucket)
    key = f"notes/2026/09/{_hex(1)}.pdf"

    storage.save(key, b"%PDF-fake-bytes")
    assert bucket.objects[key] == b"%PDF-fake-bytes"

    fileobj = storage.open(key)
    assert fileobj.read() == b"%PDF-fake-bytes"
    fileobj.close()

    storage.delete(key)
    assert key not in bucket.objects
    # Exactly one real delete — no blind multi-delete, no extra API hits.
    assert bucket.delete_misses == []


def test_s3_open_missing_key_raises_storage_error() -> None:
    storage = make_storage(FakeS3Bucket())
    with pytest.raises(StorageError, match="missing"):
        storage.open(f"notes/2026/09/{_hex(2)}.pdf")


def test_s3_provider_errors_surface_as_storage_error() -> None:
    bucket = FakeS3Bucket()
    bucket.errors["get_object"] = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "nope"}}, "GetObject"
    )
    storage = make_storage(bucket)
    with pytest.raises(StorageError):
        storage.open(f"notes/2026/09/{_hex(3)}.pdf")


def test_s3_delete_is_idempotent_but_observed() -> None:
    bucket = FakeS3Bucket()
    storage = make_storage(bucket)
    key = f"notes/2026/09/{_hex(4)}.pdf"
    storage.delete(key)  # never present
    assert bucket.delete_misses == [key]


def test_s3_save_failure_closes_stream_exactly_once() -> None:
    bucket = FakeS3Bucket()
    bucket.errors["put_object"] = ClientError(
        {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
    )
    storage = make_storage(bucket)

    class _ClosedFlagStream:
        def __init__(self) -> None:
            self.close_count = 0

        def read(self, amt: int = -1) -> bytes:
            return b"%PDF-x"

        def close(self) -> None:
            self.close_count += 1

    stream = _ClosedFlagStream()
    with pytest.raises(StorageError):
        storage.save(f"notes/2026/09/{_hex(5)}.pdf", stream)  # type: ignore[arg-type]
    assert stream.close_count == 1
    assert not bucket.objects


def test_s3_boot_check_success_and_failure() -> None:
    bucket = FakeS3Bucket()
    storage = make_storage(bucket)
    storage.boot_check()
    assert not bucket.objects  # probe written and removed

    bucket2 = FakeS3Bucket()
    bucket2.errors["put_object"] = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject"
    )
    with pytest.raises(StorageError, match="boot check"):
        make_storage(bucket2).boot_check()


# ---------------------------------------------------------------------------
# Route wiring: the HTTP flow must actually go through the configured backend.
# ---------------------------------------------------------------------------


def test_note_lifecycle_roundtrips_through_s3(
    monkeypatch: pytest.MonkeyPatch,
    client: Any,
    user_factory: Any,
    make_pdf: Any,
    subject_id: int,
) -> None:
    bucket = FakeS3Bucket()
    monkeypatch.setattr(storage_module, "_storage", make_storage(bucket))
    user = user_factory("s3roundtrip")

    try:
        # Upload → exactly one object stored.
        r = client.post(
            "/notes",
            headers=user["headers"],
            data={"subject_id": str(subject_id), "title": "S3 note"},
            files={"file": ("s3.pdf", make_pdf("s3rt"), "application/pdf")},
        )
        assert r.status_code == 201, r.text
        note_id = r.json()["id"]
        assert len(bucket.objects) == 1
        (key, stored) = next(iter(bucket.objects.items()))
        assert key.startswith("notes/") and key.endswith(".pdf")
        assert stored == make_pdf("s3rt").read()

        # Download → same bytes come back out.
        r = client.get(f"/notes/{note_id}/download", headers=user["headers"])
        assert r.status_code == 200, r.text
        assert r.content == stored

        # Delete → object really removed from storage.
        r = client.delete(f"/notes/{note_id}", headers=user["headers"])
        assert r.status_code == 200, r.text
        assert not bucket.objects
    finally:
        storage_module.reset_storage()


def test_failed_s3_save_leaves_no_orphan_and_no_reward(
    monkeypatch: pytest.MonkeyPatch,
    client: Any,
    user_factory: Any,
    make_pdf: Any,
    subject_id: int,
) -> None:
    bucket = FakeS3Bucket()
    bucket.errors["put_object"] = ClientError(
        {"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject"
    )
    monkeypatch.setattr(storage_module, "_storage", make_storage(bucket))
    user = user_factory("s3fail")

    try:
        r = client.post(
            "/notes",
            headers=user["headers"],
            data={"subject_id": str(subject_id), "title": "doomed"},
            files={"file": ("doomed.pdf", make_pdf("s3fail"), "application/pdf")},
        )
        assert r.status_code == 500, r.text
        assert not bucket.objects  # nothing half-written anywhere

        # The rolled-back transaction must not have paid the upload reward.
        r = client.get("/coins/balance", headers=user["headers"])
        assert r.status_code == 200, r.text
        assert r.json()["balance"] == 0
    finally:
        storage_module.reset_storage()
