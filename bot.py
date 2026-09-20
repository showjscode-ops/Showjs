from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import BOT_TOKEN, TELEGRAM_API_BASE
from middlewares.subscription import SubscriptionMiddleware
import asyncio

class TrackedBot(Bot):
    async def send_message(self, *args, **kwargs):
        msg = await super().send_message(*args, **kwargs)
        _track_message(msg)
        return msg

_session = None
if TELEGRAM_API_BASE:
    _session = AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_BASE))
bot = TrackedBot(
    BOT_TOKEN,
    session=_session,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher()
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())


def _loading_markup(markup: InlineKeyboardMarkup, target: CallbackQuery):
    """Return a copy of the markup with the pressed callback button showing Loading."""
    if not markup or not target.message:
        return markup, False
    rows = []
    changed = False
    target_data = target.data
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data == target_data and not changed:
                new_row.append(btn.model_copy(update={"text": "⏳ Loading…"}))
                changed = True
            else:
                new_row.append(btn)
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows), changed


# Per-chat message tracker. It records messages sent by this bot so callback
# actions can remove stale prompts/menus before showing the next screen.
# Only a bounded recent set is kept to avoid unbounded memory growth.
_TRACKED_MESSAGES = {}
_TRACKED_LIMIT = 80

def _track_message(msg):
    try:
        chat_id = msg.chat.id
        mid = msg.message_id
        bucket = _TRACKED_MESSAGES.setdefault(chat_id, [])
        if mid not in bucket:
            bucket.append(mid)
        if len(bucket) > _TRACKED_LIMIT:
            del bucket[:-_TRACKED_LIMIT]
    except Exception:
        pass
    return msg

async def _delete_stale_messages(bot, chat_id, keep_id=None):
    ids = list(_TRACKED_MESSAGES.get(chat_id, []))
    if not ids:
        return
    kept = []
    for mid in ids:
        if keep_id is not None and mid == keep_id:
            kept.append(mid)
            continue
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            # Message may already be deleted / too old / not deletable.
            pass
    _TRACKED_MESSAGES[chat_id] = kept

class MessageTrackerMiddleware:
    """Track bot replies and clear stale bot messages when a callback is clicked."""
    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        # We intentionally don't delete before the handler: the callback
        # handler often edits event.message in place.
        return result

class ButtonLoadingMiddleware:
    """Show loading directly inside the clicked inline button.

    No extra message and no floating callback alert are generated. The
    handler remains responsible for replacing/editing the message when its
    work finishes. If the handler leaves the message untouched, the original
    keyboard is restored automatically.
    """
    async def __call__(self, handler, event, data):
        if not isinstance(event, CallbackQuery) or not event.message:
            return await handler(event, data)

        original_markup = event.message.reply_markup
        loading_markup, changed = _loading_markup(original_markup, event)
        if not changed:
            return await handler(event, data)

        try:
            await event.message.edit_reply_markup(reply_markup=loading_markup)
        except Exception:
            pass

        # Remove stale bot messages from previous screens while preserving
        # the message whose button was clicked; handlers may edit it.
        try:
            await _delete_stale_messages(event.bot, event.message.chat.id, keep_id=event.message.message_id)
        except Exception:
            pass

        result = await handler(event, data)
        return result


dp.callback_query.middleware(ButtonLoadingMiddleware())

class MaintenanceMiddleware:
    async def __call__(self, handler, event, data):
        try:
            from database import get_pool
            from config import OWNER_ID,ADMIN_IDS
            uid=getattr(getattr(event,'from_user',None),'id',0)
            if uid and (uid==OWNER_ID or uid in ADMIN_IDS):
                return await handler(event,data)
            maintenance=str(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='maintenance'") or 'off').lower()
            if maintenance=='on':
                if isinstance(event, CallbackQuery):
                    await event.answer('🛠 Bot sedang maintenance.',show_alert=True)
                else:
                    await event.answer('🛠 Bot sedang maintenance. Silakan coba lagi nanti.')
                return
        except Exception:
            pass
        return await handler(event,data)

dp.message.middleware(MaintenanceMiddleware())
dp.callback_query.middleware(MaintenanceMiddleware())


from handlers.start import router as start
from handlers.upfile import router as up
from handlers.getfile import router as getf
from handlers.payments import router as pay
from handlers.vip import router as vip
from handlers.creator import router as creator
from handlers.withdraw import router as wd
from handlers.misc import router as misc
from handlers.admin import router as admin
from handlers.trial import router as trial

for r in [start, up, getf, pay, vip, creator, wd, admin, misc, trial]:
    dp.include_router(r)
