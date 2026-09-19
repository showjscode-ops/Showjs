import asyncio,logging
from database import get_pool
from utils.bayargg import BayarGG
from utils.cashi import Cashi
from utils.payments import finalize_purchase
logger=logging.getLogger(__name__)
async def worker():
 while True:
  try:
   p=await get_pool(); rows=await p.fetch("SELECT * FROM purchases WHERE status='pending' AND created_at>NOW()-INTERVAL '2 hours' ORDER BY id LIMIT 30")
   for r in rows:
    result=await (BayarGG.check_payment(r['invoice_id']) if r['provider']=='bayargg' else Cashi.check_payment(r['invoice_id']))
    if result and result['status'] in {'paid','success','completed','settled'}: await finalize_purchase(r['invoice_id'],result.get('amount') or None)
  except Exception: logger.exception('payment worker')
  await asyncio.sleep(15)
