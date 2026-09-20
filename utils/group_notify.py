from __future__ import annotations
import html
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CODE_GROUP_ID, BOT_USERNAME

def code_url(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={code}"

async def notify_code_opened(bot, code: str, user_id: int, username: str | None = None, full_name: str | None = None):
    if not CODE_GROUP_ID:
        return
    name = (full_name or username or "User").strip()[:80]
    user_line = f"User ID: <code>{int(user_id)}</code>"
    if username:
        user_line += f" (@{html.escape(username.lstrip('@'))})"
    text = (
        "CODE BERHASIL DIBUKA\n\n"
        f"{user_line}\n"
        f"Code: <code>{html.escape(code)}</code>\n"
        f"Nama: <b>{html.escape(name)}</b>"
    )
    try:
        await bot.send_message(CODE_GROUP_ID, text, parse_mode="HTML")
    except Exception:
        pass

async def notify_code_detected(bot, group_message, code: str):
    """Reply in the configured code group when a member posts a valid code.
    The callback is intentionally user-specific at click time: each Telegram
    user must have started the bot before the bot can send the private flow.
    """
    if not CODE_GROUP_ID or group_message.chat.id != CODE_GROUP_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GET FILE", callback_data=f"groupget:{code}")]
    ])
    text = (
        "CODE TERDETEKSI\n\n"
        f"User ID: <code>{int(group_message.from_user.id)}</code>\n"
        f"Code: <code>{html.escape(code)}</code>\n\n"
        "Tekan GET FILE. Media hanya akan dikirim ke chat pribadi dengan bot."
    )
    try:
        await group_message.reply(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
