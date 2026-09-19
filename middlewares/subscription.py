from __future__ import annotations
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from typing import Any, Awaitable, Callable, Dict
from config import (
    FORCE_CHANNEL_ID, NOTICE_SUB_CHANNEL_ID,
    FORCE_CHANNEL_URL, NOTICE_SUB_CHANNEL_URL,
    FORCE_CHANNEL_USERNAME, NOTICE_SUB_CHANNEL_USERNAME,
    OWNER_ID, ADMIN_IDS,
)

def _url(explicit: str, username: str, fallback_id: int) -> str:
    if explicit:
        return explicit
    if username:
        return f"https://t.me/{username}"
    # Private-channel fallback is intentionally only a join button with no guessed URL.
    return ""

async def _joined(bot, chat_id: int, user_id: int) -> bool:
    if not chat_id:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = getattr(member, "status", "")
        if status in {"creator", "administrator", "member"}:
            return True
        if status == "restricted":
            return bool(getattr(member, "is_member", False))
        return False
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    except Exception:
        return False

async def missing_subscription_channels(bot, user_id: int):
    missing = []
    if FORCE_CHANNEL_ID and not await _joined(bot, FORCE_CHANNEL_ID, user_id):
        missing.append(("📢 Channel Saluran", _url(FORCE_CHANNEL_URL, FORCE_CHANNEL_USERNAME, FORCE_CHANNEL_ID)))
    if NOTICE_SUB_CHANNEL_ID and not await _joined(bot, NOTICE_SUB_CHANNEL_ID, user_id):
        missing.append(("🔔 Notic Saluran", _url(NOTICE_SUB_CHANNEL_URL, NOTICE_SUB_CHANNEL_USERNAME, NOTICE_SUB_CHANNEL_ID)))
    return missing

async def subscription_prompt(bot, chat_id: int, user_id: int):
    missing = await missing_subscription_channels(bot, user_id)
    if not missing:
        return True
    rows = []
    for label, url in missing:
        if url:
            rows.append([InlineKeyboardButton(text=label, url=url)])
    rows.append([InlineKeyboardButton(text="✅ Saya Sudah Join", callback_data="verify_join")])
    text = "⚠️ <b>Wajib Join Dulu</b>\n\nSilakan masuk ke channel yang belum kamu join/yang kamu sudah keluar, lalu tekan <b>Saya Sudah Join</b>."
    await bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    return False

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]], event: Any, data: Dict[str, Any]):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        if user.id == OWNER_ID or user.id in ADMIN_IDS:
            return await handler(event, data)
        # Only enforce subscriptions in private chat.
        chat = getattr(event, "chat", None)
        if chat is not None and getattr(chat, "type", None) != "private":
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "verify_join":
            return await handler(event, data)
        if await subscription_prompt(event.bot, user.id, user.id):
            return await handler(event, data)
        return None
