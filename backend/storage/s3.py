"""S3-compatible storage backend (S3, Cloudflare R2, Backblaze B2, MinIO...).

Lets note files live in object storage so they survive container restarts and
redeploys (free PaaS disks are ephemeral — see README §7). Drops in behind the
same StorageBackend protocol as LocalStorage: identical key contract (shared
pattern in interface.py), identical StorageError-only failure mode.

Stream handling (mirrors local.py's atomic-write guarantees):
* save(): the caller hands us a positioned, ready-to-read stream (a seekable
  SpooledTemporaryFile). It is closed here exactly once, success or failure,
  so note_service.create_note needs no changes. botocore's standard retry mode
  rewinds seekable bodies between attempts, so a transient network error
  retries transparently without re-reading past EOF.
* open(): returns botocore's StreamingBody — bytes arrive in network-sized
  chunks, so a 25 MB note costs ~100 KB of RAM while streaming, and the
  download route can keep using StreamingResponse unchanged.

Deletes on S3-compatible stores are not read-after-write consistent: a 204 can
precede visibility. boot_check() and delete() therefore verify, so problems
surface at boot or in logs — never silently.
"""

from __future__ import annotations

import logging
import time
from typing import BinaryIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .interface import StorageError, safe_close, validate_key

logger = logging.getLogger(__name__)

# Error codes returned for missing objects. GET → "NoSuchKey"; HEAD (no body)
# and several providers → "404"/"NotFound" (R2/B2/MinIO all seen in the wild).
_MISSING_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


def _is_missing(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code", "") in _MISSING_CODES


class S3Storage:
    """Stores validated note files in an S3-compatible bucket."""

    def __init__(
        self,
        *,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
        region: str = "auto",
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=BotoConfig(
                # Standard mode retries transient errors (with body rewind for
                # seekable streams); timeouts fail fast enough for a request.
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
                # Path-style bucket addressing: required by Supabase's S3
                # gateway and MinIO, and works on AWS/R2/B2 too. Without it,
                # botocore would build bucket.<ref>.supabase.co hostnames.
                s3={"addressing_style": "path"},
            ),
        )

    # --- StorageBackend protocol ------------------------------------------

    def save(self, key: str, fileobj: BinaryIO) -> None:
        validate_key(key)
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=fileobj, ContentType="application/pdf"
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"S3 save failed for {key!r}: {exc}") from exc
        finally:
            safe_close(fileobj)

    def open(self, key: str) -> BinaryIO:
        validate_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if _is_missing(exc):
                raise StorageError("stored file is missing") from exc
            raise StorageError(f"S3 open failed for {key!r}: {exc}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"S3 open failed for {key!r}: {exc}") from exc
        return response["Body"]  # StreamingBody: readable, chunked, closeable

    def delete(self, key: str) -> None:
        validate_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"S3 delete failed for {key!r}: {exc}") from exc
        # Verification only — a failed check never turns an acknowledged
        # delete into an error; it gets logged instead.
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            try:
                if not self._exists(key):
                    return
            except (BotoCoreError, ClientError):
                return  # verification hiccup; the delete itself succeeded
            time.sleep(0.25)
        logger.warning("S3 delete: %r still readable after 4s (provider flakiness?)", key)

    # --- boot-time connectivity proof --------------------------------------

    def boot_check(self) -> None:
        """Prove credentials + bucket work at startup; never run per-request.

        Raises StorageError so get_storage() can fail the process fast — a
        misconfigured bucket should be obvious on deploy, not at first upload.
        """
        probe = f".boot-check/{time.time_ns()}"
        try:
            self._client.put_object(Bucket=self._bucket, Key=probe, Body=b"0")
            self._client.delete_object(Bucket=self._bucket, Key=probe)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(
                f"S3 boot check failed for bucket {self._bucket!r}: {exc}"
            ) from exc
        logger.info("S3 storage boot check passed (bucket=%s)", self._bucket)

    # --- internals ----------------------------------------------------------

    def _exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if _is_missing(exc):
                return False
            raise
