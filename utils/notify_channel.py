from config import NOTIF_CHANNEL_ID
async def notify(bot,text):
    if not NOTIF_CHANNEL_ID: return
    try: await bot.send_message(NOTIF_CHANNEL_ID,text,parse_mode="HTML")
    except Exception: pass
