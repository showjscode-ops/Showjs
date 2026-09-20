import hmac,hashlib,logging
from fastapi import APIRouter,Request
from config import BAYARGG_WEBHOOK_SECRET
from utils.payments import finalize_purchase
router=APIRouter(prefix='/bayargg'); log=logging.getLogger(__name__)
@router.post('/webhook')
async def webhook(request:Request):
 body=await request.body()
 sig=request.headers.get('X-Webhook-Signature') or request.headers.get('X-Callback-Signature') or ''
 if BAYARGG_WEBHOOK_SECRET:
  expected=hmac.new(BAYARGG_WEBHOOK_SECRET.encode(),body,hashlib.sha256).hexdigest()
  if not hmac.compare_digest(sig,expected): return {'success':False,'message':'invalid signature'}
 try: d=await request.json()
 except Exception: return {'success':False,'message':'invalid json'}
 event=str(d.get('event') or d.get('type') or '').lower()
 status=str(d.get('status') or d.get('payment_status') or '').lower()
 if event and event not in {'payment.paid','paid','payment.success','payment.completed'} and status not in {'paid','success','completed','settled'}: return {'success':True,'message':'ignored'}
 if status not in {'paid','success','completed','settled'}: return {'success':True,'message':'ignored'}
 inv=str(d.get('invoice_id') or d.get('invoice') or d.get('id') or request.headers.get('X-Invoice-ID') or '')
 amount=d.get('final_amount') or d.get('amount')
 ok=await finalize_purchase(inv,int(amount) if amount else None)
 return {'success':bool(ok),'message':'processed' if ok else 'invoice_not_found'}
