import asyncio, logging
from datetime import timedelta
from database import get_pool
from bot import bot
from config import OWNER_ID, ADMIN_IDS
from middlewares.subscription import missing_subscription_channels

async def worker():
    while True:
        try:
            p=await get_pool()
            rows=await p.fetch("""
                SELECT user_id, subscription_notice_at
                FROM users
                WHERE last_seen > NOW()-INTERVAL '7 days'
                  AND user_id <> $1
                ORDER BY last_seen DESC
                LIMIT 200
            """, OWNER_ID)
            for r in rows:
                uid=int(r["user_id"])
                if uid in ADMIN_IDS:
                    continue
                missing=await missing_subscription_channels(bot,uid)
                if not missing:
                    if r["subscription_notice_at"] is not None:
                        await p.execute("UPDATE users SET subscription_notice_at=NULL WHERE user_id=$1",uid)
                    continue
                last=r["subscription_notice_at"]
                if last is not None:
                    age=await p.fetchval("SELECT NOW()-$1::timestamptz",last)
                    if age is not None and age < timedelta(hours=6):
                        continue
                rows_kb=[]
                for label,url in missing:
                    if url:
                        from aiogram.types import InlineKeyboardButton
                        rows_kb.append([InlineKeyboardButton(text=label,url=url)])
                from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
                rows_kb.append([InlineKeyboardButton(text="✅ Saya Sudah Join",callback_data="verify_join")])
                try:
                    await bot.send_message(uid,
                        "⚠️ <b>Kamu keluar dari channel wajib.</b>\n\nSilakan join kembali ke channel yang belum kamu ikuti agar bot bisa digunakan.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows_kb))
                    await p.execute("UPDATE users SET subscription_notice_at=NOW() WHERE user_id=$1",uid)
                except Exception:
                    pass
        except Exception:
            logging.exception("subscription worker")
        await asyncio.sleep(600)
