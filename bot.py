from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import BOT_TOKEN
from middlewares.subscription import SubscriptionMiddleware
import asyncio

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
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

        try:
            result = await handler(event, data)
        finally:
            # If the handler did not replace the message/keyboard, restore it.
            # If it did, Telegram will reject this harmlessly and we leave the
            # handler's final UI intact.
            try:
                await event.message.edit_reply_markup(reply_markup=original_markup)
            except Exception:
                pass
        return result


dp.callback_query.middleware(ButtonLoadingMiddleware())

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

for r in [start, up, getf, pay, vip, creator, wd, misc, admin, trial]:
    dp.include_router(r)
