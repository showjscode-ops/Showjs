from __future__ import annotations
import os
from aiogram.types import FSInputFile
from utils.b2_storage import b2_pool
async def deliver_one(bot,chat_id,media,caption=None):
    path,meta=await b2_pool.download(int(media["drive_account"]),str(media["drive_file_id"]))
    try:
        typ=str(media.get("type") or "document").lower(); inp=FSInputFile(path)
        if typ=="photo": return await bot.send_photo(chat_id,inp,caption=caption)
        if typ=="video": return await bot.send_video(chat_id,inp,caption=caption)
        if typ=="audio": return await bot.send_audio(chat_id,inp,caption=caption)
        return await bot.send_document(chat_id,inp,caption=caption)
    finally:
        try: os.remove(path)
        except OSError: pass
