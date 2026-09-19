import uuid,httpx
from datetime import datetime,timezone
from config import CASHI_API_KEY,CASHI_BASE_URL,CASHI_PAYMENT_CHANNEL,CASHI_MIN_AMOUNT,CASHI_MAX_AMOUNT
class Cashi:
 @staticmethod
 async def create_payment(amount,description,customer_name="Customer"):
    if not CASHI_API_KEY or not CASHI_MIN_AMOUNT<=int(amount)<=CASHI_MAX_AMOUNT:return None
    order=f"FILE-{uuid.uuid4().hex[:16]}"; body={"amount":int(amount),"order_id":order,"kode_channel":CASHI_PAYMENT_CHANNEL}
    try:
      async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(f"{CASHI_BASE_URL}/api/create-order",json=body,headers={"x-api-key":CASHI_API_KEY,"Content-Type":"application/json","Accept":"application/json"}); r.raise_for_status(); d=r.json()
      if not d.get("success"):return None
      oid=str(d.get("orderId") or d.get("order_id") or order); qr=d.get("qrUrl")
      if not qr:return None
      return {"invoice_id":oid,"order_id":oid,"qr_string":qr,"amount":int(d.get("amount") or amount),"payment_url":d.get("checkout_url")}
    except Exception:return None
 @staticmethod
 async def check_payment(order_id):
    if not CASHI_API_KEY:return None
    try:
      async with httpx.AsyncClient(timeout=30) as c:
        r=await c.get(f"{CASHI_BASE_URL}/api/check-status/{order_id}",headers={"x-api-key":CASHI_API_KEY,"Accept":"application/json"}); r.raise_for_status(); d=r.json()
      if not d.get("success"):return None
      return {"invoice_id":str(d.get("order_id") or order_id),"status":str(d.get("status") or "").lower(),"amount":int(d.get("amount") or 0)}
    except Exception:return None
