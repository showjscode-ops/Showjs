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
        async with self._lock:
            ordered = (
                [
                    self.services[(self._cursor + i) % len(self.services)]
                    for i in range(len(self.services))
                ]
                if self.services
                else []
            )
            if self.services:
                self._cursor = (self._cursor + 1) % len(self.services)

        if not ordered:
            raise RuntimeError("No Google Drive configured")

        last = None

        for idx, svc, folder in ordered:
            for attempt in range(1, UPLOAD_RETRIES + 1):
                try:
                    # A fresh resumable request is created for every retry.
                    # This avoids reusing a broken SSL/HTTP connection.
                    def run(current_svc=svc, current_folder=folder):
                        body = {"name": filename}
                        if current_folder:
                            body["parents"] = [current_folder]

                        media = MediaFileUpload(
                            path,
                            mimetype=mime or "application/octet-stream",
                            resumable=True,
                            chunksize=UPLOAD_CHUNK_SIZE,
                        )

                        request = current_svc.files().create(
                            body=body,
                            media_body=media,
                            fields="id,name,size,mimeType",
                        )

                        response = None
                        while response is None:
                            _, response = request.next_chunk(
                                num_retries=2
                            )

                        return response

                    result = await asyncio.to_thread(run)

                    # Confirm the file is visible to the same Drive service.
                    verified = await asyncio.to_thread(
                        lambda: svc.files()
                        .get(
                            fileId=result["id"],
                            fields="id,name,size,mimeType",
                        )
                        .execute()
                    )

                    logger.info(
                        "Drive %s upload success: id=%s name=%s",
                        idx,
                        verified.get("id"),
                        verified.get("name"),
                    )
                    return idx, verified["id"], verified

                except Exception as e:
                    last = e
                    logger.warning(
                        "Drive %s upload attempt %s/%s failed: %s",
                        idx,
                        attempt,
                        UPLOAD_RETRIES,
                        repr(e),
                    )

                    # Rebuild the HTTP/service object after transport/SSL
                    # failures. This is especially useful on Railway.
                    try:
                        svc, folder = self._rebuild_service(idx)
                    except Exception:
                        logger.exception(
                            "Drive %s service rebuild failed", idx
                        )

                    if attempt < UPLOAD_RETRIES:
                        await asyncio.sleep(min(2 ** (attempt - 1), 8))

            logger.error("Drive %s upload failed after retries", idx)

        raise last or RuntimeError("Drive upload failed")

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
