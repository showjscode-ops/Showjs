from config import NOTIF_CHANNEL_ID, ERROR_NOTICE_CHAT_ID

async def notify(bot,text):
    target=ERROR_NOTICE_CHAT_ID or NOTIF_CHANNEL_ID
    if not target: return
    try:
        await bot.send_message(target,text,parse_mode="HTML")
    except Exception:
        pass
