from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import credentials as oauth_credentials
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
TOKEN_URI = "https://oauth2.googleapis.com/token"

# Smaller chunks reduce the chance of a broken TLS connection on Railway.
UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
UPLOAD_RETRIES = 4
REQUEST_TIMEOUT = (30, 180)


class DriveAccount:
    def __init__(self, account_id, folder_id, creds):
        self.account_id = int(account_id)
        self.folder_id = folder_id
        self.creds = creds
        self.session = AuthorizedSession(creds)

    def rebuild_session(self):
        self.session.close()
        self.session = AuthorizedSession(self.creds)


class DrivePool:
    """
    Google Drive storage pool.

    OAuth (recommended for normal Gmail/My Drive):
      GOOGLE_DRIVE_N_CLIENT_ID
      GOOGLE_DRIVE_N_CLIENT_SECRET
      GOOGLE_DRIVE_N_REFRESH_TOKEN
      GOOGLE_DRIVE_N_FOLDER_ID

    Service Account fallback:
      GOOGLE_DRIVE_N_JSON
      GOOGLE_DRIVE_N_FOLDER_ID

    Up to 10 accounts are supported.
    """

    def __init__(self):
        self.accounts = []
        self._lock = asyncio.Lock()
        self._cursor = 0
        self._load()

    def _load(self):
        for i in range(1, 11):
            folder = os.getenv(f"GOOGLE_DRIVE_{i}_FOLDER_ID", "").strip()
            client_id = os.getenv(f"GOOGLE_DRIVE_{i}_CLIENT_ID", "").strip()
            client_secret = os.getenv(
                f"GOOGLE_DRIVE_{i}_CLIENT_SECRET", ""
            ).strip()
            refresh_token = os.getenv(
                f"GOOGLE_DRIVE_{i}_REFRESH_TOKEN", ""
            ).strip()

            # OAuth takes priority. This is required for ordinary Gmail My Drive.
            if client_id and client_secret and refresh_token:
                try:
                    creds = oauth_credentials.Credentials(
                        token=None,
                        refresh_token=refresh_token,
                        token_uri=TOKEN_URI,
                        client_id=client_id,
                        client_secret=client_secret,
                        scopes=SCOPES,
                    )
                    # Refresh once at startup so invalid credentials fail early.
                    creds.refresh(__import__("google.auth.transport.requests", fromlist=["Request"]).Request())
                    account = DriveAccount(i, folder, creds)
                    self.accounts.append(account)
                    logger.info("Google Drive %s loaded using OAuth", i)
                    continue
                except Exception:
                    logger.exception("Google Drive %s OAuth init failed", i)

            # Legacy/shared-drive fallback.
            raw = os.getenv(f"GOOGLE_DRIVE_{i}_JSON", "").strip()
            if raw:
                try:
                    info = json.loads(raw)
                    creds = service_account.Credentials.from_service_account_info(
                        info, scopes=SCOPES
                    )
                    account = DriveAccount(i, folder, creds)
                    self.accounts.append(account)
                    logger.info(
                        "Google Drive %s loaded using Service Account fallback",
                        i,
                    )
                except Exception:
                    logger.exception(
                        "Google Drive %s Service Account init failed", i
                    )

        logger.info(
            "Google Drive accounts available: %s",
            [a.account_id for a in self.accounts],
        )

    @property
    def available(self):
        return bool(self.accounts)

    def _account(self, account_id):
        for account in self.accounts:
            if account.account_id == int(account_id):
                return account
        raise RuntimeError(f"Google Drive account {account_id} unavailable")

    @staticmethod
    def _raise_http(response):
        if response.ok:
            return
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1000]
        raise RuntimeError(
            f"Google Drive HTTP {response.status_code}: {detail}"
        )

    async def _new_session(self, account, filename, mime, size):
        def create():
            metadata = {
                "name": filename,
                "mimeType": mime or "application/octet-stream",
            }
            if account.folder_id:
                metadata["parents"] = [account.folder_id]

            url = (
                f"{UPLOAD_API}?uploadType=resumable"
                f"&supportsAllDrives=true"
            )
            headers = {
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime or "application/octet-stream",
                "X-Upload-Content-Length": str(size),
            }
            response = account.session.post(
                url,
                headers=headers,
                json=metadata,
                timeout=REQUEST_TIMEOUT,
            )
            self._raise_http(response)
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError(
                    "Google Drive did not return a resumable upload Location"
                )
            return location

        return await asyncio.to_thread(create)

    async def _upload_once(self, account, snapshot, filename, mime, size):
        # New session for every attempt.
        session_url = await self._new_session(
            account, filename, mime, size
        )

        def run():
            offset = 0
            with open(snapshot, "rb") as fh:
                while offset < size:
                    chunk = fh.read(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        raise RuntimeError(
                            f"Unexpected EOF at {offset}/{size}"
                        )

                    start = offset
                    end = offset + len(chunk) - 1
                    headers = {
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end}/{size}",
                        "Content-Type": mime or "application/octet-stream",
                    }

                    response = account.session.put(
                        session_url,
                        headers=headers,
                        data=chunk,
                        timeout=REQUEST_TIMEOUT,
                    )

                    # 308 means Google accepted this chunk and wants more.
                    if response.status_code == 308:
                        range_header = response.headers.get("Range", "")
                        if range_header.startswith("bytes="):
                            try:
                                server_end = int(
                                    range_header.split("-", 1)[1]
                                )
                                offset = server_end + 1
                                fh.seek(offset)
                                continue
                            except Exception:
                                pass

                        offset = end + 1
                        continue

                    self._raise_http(response)

                    if response.status_code in (200, 201):
                        try:
                            return response.json()
                        except Exception:
                            return {}

                    raise RuntimeError(
                        f"Unexpected resumable upload status "
                        f"{response.status_code}"
                    )

            raise RuntimeError("Upload ended without a completed response")

        return await asyncio.to_thread(run)

    async def _get_metadata(self, account, file_id):
        def run():
            response = account.session.get(
                f"{DRIVE_API}/files/{file_id}",
                params={
                    "fields": "id,name,mimeType,size",
                    "supportsAllDrives": "true",
                },
                timeout=REQUEST_TIMEOUT,
            )
            self._raise_http(response)
            return response.json()

        return await asyncio.to_thread(run)

    async def upload(self, path, filename, mime):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        expected = os.path.getsize(path)
        if expected <= 0:
            raise RuntimeError("Cannot upload an empty file")

        # Immutable snapshot prevents the Telegram temp file from changing
        # while Drive is reading it.
        fd, snapshot = tempfile.mkstemp(
            prefix="drive_snapshot_", suffix=".bin"
        )
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
                        "No Google Drive configured. Configure "
                        "GOOGLE_DRIVE_1_CLIENT_ID, "
                        "GOOGLE_DRIVE_1_CLIENT_SECRET, "
                        "GOOGLE_DRIVE_1_REFRESH_TOKEN and "
                        "GOOGLE_DRIVE_1_FOLDER_ID."
                    )
                ordered = [
                    self.accounts[
                        (self._cursor + n) % len(self.accounts)
                    ]
                    for n in range(len(self.accounts))
                ]
                self._cursor = (self._cursor + 1) % len(self.accounts)

            last = None

            for account in ordered:
                for attempt in range(1, UPLOAD_RETRIES + 1):
                    try:
                        result = await self._upload_once(
                            account, snapshot, filename, mime, size
                        )

                        file_id = result.get("id")
                        if not file_id:
                            raise RuntimeError(
                                f"Drive upload returned no file id: {result}"
                            )

                        verified = await self._get_metadata(
                            account, file_id
                        )
                        remote_size = int(verified.get("size") or 0)
                        if remote_size != size:
                            raise RuntimeError(
                                "Drive upload size verification failed: "
                                f"local={size}, remote={remote_size}"
                            )

                        logger.info(
                            "Drive %s upload success: id=%s size=%s",
                            account.account_id,
                            file_id,
                            remote_size,
                        )
                        return (
                            account.account_id,
                            file_id,
                            verified,
                        )

                    except Exception as exc:
                        last = exc
                        low = str(exc).lower()
                        logger.warning(
                            "Drive %s upload attempt %s/%s failed: %s",
                            account.account_id,
                            attempt,
                            UPLOAD_RETRIES,
                            exc,
                        )

                        # These errors won't improve by retrying the same
                        # credentials/session.
                        deterministic = any(
                            marker in low
                            for marker in (
                                "storagequotaexceeded",
                                "service accounts do not have storage quota",
                                "invalid_grant",
                                "unauthorized_client",
                                "invalid_client",
                                "invalid authentication credentials",
                            )
                        )
                        if deterministic:
                            break

                        # Rebuild only the requests session, never
                        # googleapiclient/httplib2. This avoids the SSL
                        # segfault stack seen on Railway.
                        try:
                            await asyncio.to_thread(
                                account.rebuild_session
                            )
                        except Exception:
                            logger.exception(
                                "Drive %s session rebuild failed",
                                account.account_id,
                            )

                        if attempt < UPLOAD_RETRIES:
                            await asyncio.sleep(min(2 ** (attempt - 1), 8))

                logger.error(
                    "Drive %s upload failed", account.account_id
                )

            raise last or RuntimeError("Drive upload failed")
        finally:
            try:
                os.remove(snapshot)
            except OSError:
                pass

    async def download(self, account_id, file_id):
        account = self._account(account_id)
        meta = await self._get_metadata(account, file_id)

        fd, path = tempfile.mkstemp(prefix="pastele_drive_")
        os.close(fd)

        def run():
            with account.session.get(
                f"{DRIVE_API}/files/{file_id}",
                params={
                    "alt": "media",
                    "supportsAllDrives": "true",
                },
                stream=True,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                self._raise_http(response)
                with open(path, "wb") as fh:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            fh.write(chunk)

        try:
            await asyncio.to_thread(run)
            return path, meta
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise

    async def delete(self, account_id, file_id):
        try:
            account = self._account(account_id)

            def run():
                response = account.session.delete(
                    f"{DRIVE_API}/files/{file_id}",
                    params={"supportsAllDrives": "true"},
                    timeout=REQUEST_TIMEOUT,
                )
                self._raise_http(response)

            await asyncio.to_thread(run)
            return True
        except Exception:
            logger.exception("Drive delete failed")
            return False


drive_pool = DrivePool()
