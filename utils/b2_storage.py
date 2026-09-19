from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from config import B2_COUNT

logger = logging.getLogger(__name__)

UPLOAD_RETRIES = 3
REQUEST_TIMEOUT = 120


@dataclass
class B2Account:
    account_id: int
    endpoint: str
    region: str
    bucket: str
    key_id: str
    application_key: str
    client: object


class B2Pool:
    """Backblaze B2 S3-compatible storage pool.

    Account 1:
      B2_ENDPOINT
      B2_REGION
      B2_BUCKET
      B2_KEY_ID
      B2_APPLICATION_KEY

    Accounts 2-10:
      B2_2_ENDPOINT ... B2_2_APPLICATION_KEY
      ...
    """

    def __init__(self):
        self.accounts: list[B2Account] = []
        self._cursor = 0
        self._lock = asyncio.Lock()
        self._load()

    @staticmethod
    def _env(account_id: int, field: str, default: str = "") -> str:
        prefix = "B2" if account_id == 1 else f"B2_{account_id}"
        return os.getenv(f"{prefix}_{field}", default).strip()

    def _load(self):
        self.accounts.clear()
        for account_id in range(1, B2_COUNT + 1):
            endpoint = self._env(account_id, "ENDPOINT").rstrip("/")
            region = self._env(account_id, "REGION")
            bucket = self._env(account_id, "BUCKET")
            key_id = self._env(account_id, "KEY_ID")
            app_key = self._env(account_id, "APPLICATION_KEY")

            if not all((endpoint, region, bucket, key_id, app_key)):
                if account_id == 1:
                    logger.warning(
                        "Backblaze B2 is not configured. "
                        "Set B2_ENDPOINT, B2_REGION, B2_BUCKET, "
                        "B2_KEY_ID and B2_APPLICATION_KEY."
                    )
                continue

            if not endpoint.startswith(("http://", "https://")):
                endpoint = "https://" + endpoint

            try:
                client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    region_name=region,
                    aws_access_key_id=key_id,
                    aws_secret_access_key=app_key,
                    config=BotoConfig(
                        signature_version="s3v4",
                        connect_timeout=30,
                        read_timeout=REQUEST_TIMEOUT,
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
                self.accounts.append(
                    B2Account(
                        account_id=account_id,
                        endpoint=endpoint,
                        region=region,
                        bucket=bucket,
                        key_id=key_id,
                        application_key=app_key,
                        client=client,
                    )
                )
                logger.info(
                    "Backblaze B2 %s loaded: bucket=%s endpoint=%s",
                    account_id, bucket, endpoint,
                )
            except Exception:
                logger.exception("Backblaze B2 %s init failed", account_id)

    @property
    def available(self) -> bool:
        return bool(self.accounts)

    def _account(self, account_id: int) -> B2Account:
        for account in self.accounts:
            if account.account_id == int(account_id):
                return account
        raise RuntimeError(f"Backblaze B2 account {account_id} is unavailable")

    @staticmethod
    def _object_key(filename: str) -> str:
        safe = Path(filename or "file.bin").name
        # Keep the original extension/name readable, while preventing path traversal.
        token = uuid.uuid4().hex
        return f"showjsbot/{token}_{safe}"

    async def upload(self, path: str, filename: str, mime: str):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        expected = os.path.getsize(path)
        if expected <= 0:
            raise RuntimeError("Cannot upload an empty file")

        fd, snapshot = tempfile.mkstemp(prefix="b2_snapshot_", suffix=".bin")
        os.close(fd)

        try:
            await asyncio.to_thread(shutil.copyfile, path, snapshot)
            size = os.path.getsize(snapshot)
            if size != expected:
                raise RuntimeError(
                    f"Snapshot size mismatch: source={expected}, snapshot={size}"
                )

            async with self._lock:
                if not self.accounts:
                    raise RuntimeError(
                        "No Backblaze B2 configured. Set B2_ENDPOINT, "
                        "B2_REGION, B2_BUCKET, B2_KEY_ID and "
                        "B2_APPLICATION_KEY."
                    )
                ordered = [
                    self.accounts[(self._cursor + n) % len(self.accounts)]
                    for n in range(len(self.accounts))
                ]
                self._cursor = (self._cursor + 1) % len(self.accounts)

            last = None
            for account in ordered:
                object_key = self._object_key(filename)
                for attempt in range(1, UPLOAD_RETRIES + 1):
                    try:
                        extra = {}
                        if mime:
                            extra["ContentType"] = mime

                        if extra:
                            await asyncio.to_thread(
                                account.client.upload_file,
                                snapshot,
                                account.bucket,
                                object_key,
                                ExtraArgs=extra,
                            )
                        else:
                            await asyncio.to_thread(
                                account.client.upload_file,
                                snapshot,
                                account.bucket,
                                object_key,
                            )

                        head = await asyncio.to_thread(
                            account.client.head_object,
                            Bucket=account.bucket,
                            Key=object_key,
                        )
                        remote_size = int(head.get("ContentLength") or 0)
                        if remote_size != size:
                            raise RuntimeError(
                                "Backblaze B2 upload size verification failed: "
                                f"local={size}, remote={remote_size}"
                            )

                        logger.info(
                            "Backblaze B2 %s upload success: key=%s size=%s",
                            account.account_id, object_key, remote_size,
                        )
                        return account.account_id, object_key, {
                            "id": object_key,
                            "name": filename,
                            "mimeType": mime or "application/octet-stream",
                            "size": remote_size,
                            "bucket": account.bucket,
                        }

                    except Exception as exc:
                        last = exc
                        logger.warning(
                            "B2 %s upload attempt %s/%s failed: %s",
                            account.account_id, attempt, UPLOAD_RETRIES, exc,
                        )
                        if attempt < UPLOAD_RETRIES:
                            await asyncio.sleep(min(2 ** (attempt - 1), 8))

                logger.error("Backblaze B2 %s upload failed", account.account_id)

            raise last or RuntimeError("Backblaze B2 upload failed")
        finally:
            try:
                os.remove(snapshot)
            except OSError:
                pass

    async def download(self, account_id, object_key):
        account = self._account(account_id)
        fd, path = tempfile.mkstemp(prefix="pastele_b2_")
        os.close(fd)

        def run():
            with open(path, "wb") as fh:
                account.client.download_fileobj(
                    account.bucket,
                    str(object_key),
                    fh,
                )

        try:
            await asyncio.to_thread(run)
            meta = await asyncio.to_thread(
                account.client.head_object,
                Bucket=account.bucket,
                Key=str(object_key),
            )
            return path, meta
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise

    async def delete(self, account_id, object_key):
        try:
            account = self._account(account_id)
            await asyncio.to_thread(
                account.client.delete_object,
                Bucket=account.bucket,
                Key=str(object_key),
            )
            return True
        except Exception:
            logger.exception("Backblaze B2 delete failed")
            return False


b2_pool = B2Pool()
# Compatibility name used by existing handlers; it now points to B2, not Backblaze B2.
drive_pool = b2_pool
