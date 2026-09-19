from fastapi import APIRouter,Request
from utils.payments import finalize_purchase
router=APIRouter(prefix='/cashi')
@router.post('/webhook')
async def webhook(request:Request):
 try:d=await request.json()
 except:return {'success':False,'message':'invalid json'}
 status=str(d.get('status') or '').lower(); inv=str(d.get('order_id') or d.get('orderId') or d.get('invoice_id') or '')
 if status not in {'paid','success','completed','settled'}:return {'success':True,'message':'ignored'}
 text=await finalize_purchase(inv,int(d.get('amount')) if d.get('amount') else None); return {'success':bool(text is not False)}
