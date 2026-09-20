import uuid,httpx,logging
from config import CASHI_API_KEY,CASHI_BASE_URL,CASHI_PAYMENT_CHANNEL,CASHI_MIN_AMOUNT,CASHI_MAX_AMOUNT
log=logging.getLogger(__name__)

class Cashi:
    @staticmethod
    async def create_payment(amount,description,customer_name="Customer"):
        if not CASHI_API_KEY or not CASHI_MIN_AMOUNT<=int(amount)<=CASHI_MAX_AMOUNT: return None
        order=f"FILE-{uuid.uuid4().hex[:16]}"
        body={"amount":int(amount),"order_id":order,"kode_channel":CASHI_PAYMENT_CHANNEL,"description":str(description)[:200],"customer_name":str(customer_name or "Customer")[:100]}
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.post(f"{CASHI_BASE_URL}/api/create-order",json=body,headers={"x-api-key":CASHI_API_KEY,"Content-Type":"application/json","Accept":"application/json"})
                raw=r.json()
                if r.status_code >= 400:
                    log.error("Cashi create HTTP %s: %s",r.status_code,raw); return None
            if not raw.get("success",True):
                log.error("Cashi create rejected: %s",raw); return None
            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            merged={**d,**raw}
            oid=str(merged.get("orderId") or merged.get("order_id") or merged.get("invoice_id") or order)
            qr=merged.get("qrUrl") or merged.get("qr_url") or merged.get("qris") or merged.get("qr_string")
            url=merged.get("checkout_url") or merged.get("payment_url") or (qr if isinstance(qr,str) and qr.startswith("http") else None)
            return {"invoice_id":oid,"order_id":oid,"qr_string":qr if isinstance(qr,str) and not qr.startswith("http") else None,"payment_url":url,"amount":int(merged.get("amount") or amount)}
        except Exception:
            log.exception("Cashi create payment failed")
            return None

    @staticmethod
    async def check_payment(order_id):
        if not CASHI_API_KEY: return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.get(f"{CASHI_BASE_URL}/api/check-status/{order_id}",headers={"x-api-key":CASHI_API_KEY,"Accept":"application/json"})
                raw=r.json()
                if r.status_code >= 400: return None
            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            merged={**d,**raw}
            return {"invoice_id":str(merged.get("order_id") or merged.get("orderId") or merged.get("invoice_id") or order_id),"status":str(merged.get("status") or merged.get("payment_status") or "").lower(),"amount":int(merged.get("amount") or 0)}
        except Exception:
            log.exception("Cashi check payment failed")
            return None
