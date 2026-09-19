import asyncio,logging
from database import get_pool
from bot import bot
async def worker():
 while True:
  try:
   p=await get_pool(); rows=await p.fetch("DELETE FROM delivery_messages WHERE expires_at<=NOW() RETURNING chat_id,message_id")
   for r in rows:
    try:await bot.delete_message(r['chat_id'],r['message_id'])
    except Exception:pass
  except Exception:logging.exception('expiry worker')
  await asyncio.sleep(60)
