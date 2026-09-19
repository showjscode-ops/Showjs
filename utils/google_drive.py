from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
UPLOAD_RETRIES = 4


class DrivePool:
    def __init__(self):
        self.services = []
        self._configs = []
        self._lock = asyncio.Lock()
        self._cursor = 0
        self._load()

    @staticmethod
    def _build_service(info):
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _load(self):
        for i in range(1, 11):
            raw = os.getenv(f"GOOGLE_DRIVE_{i}_JSON", "").strip()
            if not raw:
                continue
            try:
                info = json.loads(raw)
                folder = os.getenv(f"GOOGLE_DRIVE_{i}_FOLDER_ID", "").strip()
                svc = self._build_service(info)
                self._configs.append((i, info, folder))
                self.services.append((i, svc, folder))
            except Exception:
                logger.exception("Google Drive %s init failed", i)

        logger.info("Google Drive accounts: %s", [x[0] for x in self.services])

    @property
    def available(self):
        return bool(self.services)

    def _service(self, account):
        for i, svc, folder in self.services:
            if int(i) == int(account):
                return svc
        raise RuntimeError(f"Google Drive account {account} unavailable")

    def _rebuild_service(self, account):
        for i, info, folder in self._configs:
            if int(i) == int(account):
                svc = self._build_service(info)
                for pos, (old_i, _, old_folder) in enumerate(self.services):
                    if int(old_i) == int(account):
                        self.services[pos] = (old_i, svc, old_folder)
                        break
                else:
                    self.services.append((i, svc, folder))
                return svc, folder
        raise RuntimeError(f"Google Drive account {account} unavailable")

    async def upload(self, path, filename, mime):
        """Upload an immutable snapshot using a fresh resumable session per retry."""
        import os
        import shutil
        import tempfile

        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        expected = os.path.getsize(path)
        if expected <= 0:
            raise RuntimeError("Cannot upload an empty file")

        fd, snapshot = tempfile.mkstemp(prefix="drive_snapshot_", suffix=".bin")
        os.close(fd)
        try:
            # Snapshot prevents the Telegram temp file from changing during upload.
            await asyncio.to_thread(shutil.copyfile, path, snapshot)
            snap_size = os.path.getsize(snapshot)
            if snap_size != expected:
                raise RuntimeError(
                    f"Snapshot size mismatch: source={expected}, snapshot={snap_size}"
                )

            async with self._lock:
                if not self.services:
                    raise RuntimeError(
                        "No Google Drive configured. Configure "
                        "GOOGLE_DRIVE_1_CLIENT_ID, GOOGLE_DRIVE_1_CLIENT_SECRET, "
                        "GOOGLE_DRIVE_1_REFRESH_TOKEN and GOOGLE_DRIVE_1_FOLDER_ID."
                    )
                ordered = [
                    self.services[(self._cursor + n) % len(self.services)]
                    for n in range(len(self.services))
                ]
                self._cursor = (self._cursor + 1) % len(self.services)

            last = None
            for idx, svc, folder in ordered:
                for attempt in range(1, UPLOAD_RETRIES + 1):
                    try:
                        # Every attempt creates a brand-new resumable session.
                        def run(current_svc=svc, current_folder=folder):
                            body = {"name": filename}
                            if current_folder:
                                body["parents"] = [current_folder]

                            media = MediaFileUpload(
                                snapshot,
                                mimetype=mime or "application/octet-stream",
                                resumable=True,
                                chunksize=UPLOAD_CHUNK_SIZE,
                            )
                            req = current_svc.files().create(
                                body=body,
                                media_body=media,
                                fields="id,name,size,mimeType",
                            )

                            response = None
                            while response is None:
                                _, response = req.next_chunk(num_retries=0)
                            return response

                        result = await asyncio.to_thread(run)

                        verified = await asyncio.to_thread(
                            lambda: svc.files().get(
                                fileId=result["id"],
                                fields="id,name,size,mimeType",
                            ).execute()
                        )
                        remote_size = int(verified.get("size") or 0)
                        if remote_size != snap_size:
                            raise RuntimeError(
                                f"Drive size mismatch: local={snap_size}, "
                                f"remote={remote_size}"
                            )

                        logger.info(
                            "Drive %s upload success: id=%s size=%s",
                            idx, verified.get("id"), remote_size
                        )
                        return idx, verified["id"], verified

                    except Exception as exc:
                        last = exc
                        low = str(exc).lower()
                        logger.warning(
                            "Drive %s upload attempt %s/%s failed: %s",
                            idx, attempt, UPLOAD_RETRIES, exc
                        )

                        deterministic = any(x in low for x in (
                            "storagequotaexceeded",
                            "service accounts do not have storage quota",
                            "invalid_grant",
                            "unauthorized_client",
                            "invalid_client",
                        ))
                        if deterministic:
                            break

                        # Content-Range mismatch = discard the session and
                        # start a completely new session on the next attempt.
                        if "content-range" in low or "final size" in low:
                            logger.warning(
                                "Drive %s Content-Range mismatch; "
                                "discarding resumable session.",
                                idx
                            )

                        if attempt < UPLOAD_RETRIES:
                            try:
                                svc, folder = await asyncio.to_thread(
                                    self._rebuild_service, idx
                                )
                            except Exception:
                                logger.exception(
                                    "Drive %s service rebuild failed", idx
                                )
                            await asyncio.sleep(min(2 ** (attempt - 1), 8))

                logger.error("Drive %s upload failed", idx)

            raise last or RuntimeError("Drive upload failed")
        finally:
            try:
                os.remove(snapshot)
            except OSError:
                pass

    async def download(self, account, file_id):
        svc = self._service(account)
        fd, path = tempfile.mkstemp(prefix="pastele_drive_")
        os.close(fd)

        meta = await asyncio.to_thread(
            lambda: svc.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,size",
            )
            .execute()
        )

        def run():
            req = svc.files().get_media(fileId=file_id)
            with open(path, "wb") as fh:
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = dl.next_chunk(num_retries=2)

        try:
            await asyncio.to_thread(run)
            return path, meta
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise

    async def delete(self, account, file_id):
        try:
            svc = self._service(account)
            await asyncio.to_thread(
                lambda: svc.files().delete(fileId=file_id).execute()
            )
            return True
        except Exception:
            logger.exception("Drive delete failed")
            return False


drive_pool = DrivePool()
