import hmac,hashlib
from fastapi import APIRouter,Request
from config import BAYARGG_WEBHOOK_SECRET
from utils.payments import finalize_purchase
router=APIRouter(prefix='/bayargg')
@router.post('/webhook')
async def webhook(request:Request):
 body=await request.body(); sig=request.headers.get('X-Callback-Signature','')
 if BAYARGG_WEBHOOK_SECRET and not hmac.compare_digest(sig,hmac.new(BAYARGG_WEBHOOK_SECRET.encode(),body,hashlib.sha256).hexdigest()):return {'success':False,'message':'invalid signature'}
 try:d=await request.json()
 except:return {'success':False,'message':'invalid json'}
 if str(d.get('status','')).lower() not in {'paid','success','completed','settled'}:return {'success':True,'message':'ignored'}
 inv=str(d.get('invoice_id') or d.get('invoice') or d.get('id') or '')
 text=await finalize_purchase(inv,int(d.get('amount')) if d.get('amount') else None)
 return {'success':bool(text is not False),'message':'processed'}
