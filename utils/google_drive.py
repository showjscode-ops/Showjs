from __future__ import annotations
import asyncio,json,logging,os,tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload,MediaIoBaseDownload
logger=logging.getLogger(__name__)
SCOPES=["https://www.googleapis.com/auth/drive"]
class DrivePool:
    def __init__(self):
        self.services=[]; self._lock=asyncio.Lock(); self._cursor=0; self._load()
    def _load(self):
        for i in range(1,11):
            raw=os.getenv(f"GOOGLE_DRIVE_{i}_JSON","").strip()
            if not raw: continue
            try:
                info=json.loads(raw); creds=service_account.Credentials.from_service_account_info(info,scopes=SCOPES)
                svc=build("drive","v3",credentials=creds,cache_discovery=False)
                folder=os.getenv(f"GOOGLE_DRIVE_{i}_FOLDER_ID","").strip()
                self.services.append((i,svc,folder))
            except Exception: logger.exception("Google Drive %s init failed",i)
        logger.info("Google Drive accounts: %s",[x[0] for x in self.services])
    @property
    def available(self): return bool(self.services)
    async def upload(self,path,filename,mime):
        async with self._lock:
            ordered=[self.services[(self._cursor+i)%len(self.services)] for i in range(len(self.services))] if self.services else []
            if self.services: self._cursor=(self._cursor+1)%len(self.services)
        if not ordered: raise RuntimeError("No Google Drive configured")
        last=None
        for idx,svc,folder in ordered:
            try:
                def run():
                    body={"name":filename}
                    if folder: body["parents"]=[folder]
                    media=MediaFileUpload(path,mimetype=mime or "application/octet-stream",resumable=True)
                    return svc.files().create(body=body,media_body=media,fields="id,name,size,mimeType").execute()
                result=await asyncio.to_thread(run)
                return idx,result["id"],result
            except Exception as e:
                last=e; logger.exception("Drive %s upload failed",idx)
        raise last or RuntimeError("Drive upload failed")
    def _service(self,account):
        for i,s,f in self.services:
            if int(i)==int(account): return s
        raise RuntimeError(f"Google Drive account {account} unavailable")
    async def download(self,account,file_id):
        svc=self._service(account); fd,path=tempfile.mkstemp(prefix="pastele_drive_"); os.close(fd)
        meta=await asyncio.to_thread(lambda:svc.files().get(fileId=file_id,fields="id,name,mimeType,size").execute())
        def run():
            req=svc.files().get_media(fileId=file_id)
            with open(path,"wb") as fh:
                dl=MediaIoBaseDownload(fh,req); done=False
                while not done: _,done=dl.next_chunk()
        try: await asyncio.to_thread(run); return path,meta
        except Exception:
            try: os.remove(path)
            except OSError: pass
            raise
    async def delete(self,account,file_id):
        try:
            svc=self._service(account); await asyncio.to_thread(lambda:svc.files().delete(fileId=file_id).execute()); return True
        except Exception: logger.exception("Drive delete failed"); return False
drive_pool=DrivePool()
