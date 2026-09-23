from __future__ import annotations
import os
from aiogram.types import FSInputFile
from utils.b2_storage import b2_pool

def _value(media, *keys):
    """Read media fields safely from dict-like JSONB records."""
    for key in keys:
        try:
            value = media.get(key)
        except Exception:
            value = None
        if value:
            return value
    return None

async def deliver_one(bot, chat_id, media, caption=None):
    """Deliver B2 media. Caller should fallback to Telegram file_id on failure."""
    account = _value(media, "drive_account", "b2_account")
    key = _value(media, "drive_file_id", "b2_file_id", "storage_key")
    if account is None or not key:
        raise RuntimeError("Backblaze metadata tidak tersedia")

    path, _ = await b2_pool.download(int(account), str(key))
    try:
        typ = str(_value(media, "type", "media_type") or "document").lower()
        inp = FSInputFile(path)
        if typ == "photo":
            return await bot.send_photo(chat_id, inp, caption=caption)
        if typ == "video":
            return await bot.send_video(chat_id, inp, caption=caption)
        if typ == "audio":
            return await bot.send_audio(chat_id, inp, caption=caption)
        return await bot.send_document(chat_id, inp, caption=caption)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

async def deliver_telegram_file_id(bot, chat_id, media, caption=None):
    """Deliver the original Telegram media without downloading it."""
    fid = _value(
        media,
        "telegram_file_id",
        "file_id",
        "telegram_id",
        "telegram_file",
    )
    if not fid:
        raise RuntimeError("Telegram file_id tidak tersedia")

    typ = str(_value(media, "type", "media_type") or "document").lower()
    if typ == "photo":
        return await bot.send_photo(chat_id, fid, caption=caption)
    if typ == "video":
        return await bot.send_video(chat_id, fid, caption=caption)
    if typ == "audio":
        return await bot.send_audio(chat_id, fid, caption=caption)
    return await bot.send_document(chat_id, fid, caption=caption)
