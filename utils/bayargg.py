import httpx,re,unicodedata,logging
from config import BAYARGG_API_KEY,BAYARGG_BASE_URL

log=logging.getLogger(__name__)

def clean_name(name):
    name=unicodedata.normalize("NFKC",name or "Customer").encode("ascii","ignore").decode("ascii")
    name=re.sub(r"[^A-Za-z0-9 .,_-]","",name)
    return re.sub(r"\s+"," ",name).strip()[:50] or "Customer"

class BayarGG:
    @staticmethod
    async def create_payment(amount,description,callback_url=None,customer_name=None):
        if not BAYARGG_API_KEY: return None
        payload={
            "amount":int(amount),
            "description":str(description)[:200],
            "payment_method":"qris",
            "customer_name":clean_name(customer_name or "Customer"),
        }
        if callback_url: payload["callback_url"]=callback_url
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.post(f"{BAYARGG_BASE_URL}/create-payment.php",headers={"X-API-Key":BAYARGG_API_KEY,"Content-Type":"application/json"},json=payload)
                raw=r.json()
                if r.status_code >= 400:
                    log.error("BayarGG create HTTP %s: %s",r.status_code,raw)
                    return None
            if not raw.get("success",True):
                log.error("BayarGG create rejected: %s",raw)
                return None
            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            pay=raw.get("payment") if isinstance(raw.get("payment"),dict) else {}
            merged={**pay,**d,**raw}
            inv=merged.get("invoice_id") or merged.get("invoice") or merged.get("id")
            qr=merged.get("qris_string") or merged.get("qris") or merged.get("qr_string") or merged.get("qr")
            url=merged.get("payment_url") or merged.get("checkout_url")
            if not inv: return None
            return {"invoice_id":str(inv),"qr_string":qr,"payment_url":url,"amount":int(merged.get("final_amount") or merged.get("amount") or amount)}
        except Exception:
            log.exception("BayarGG create payment failed")
            return None

    @staticmethod
    async def check_payment(invoice):
        if not BAYARGG_API_KEY: return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.get(f"{BAYARGG_BASE_URL}/check-payment.php",headers={"X-API-Key":BAYARGG_API_KEY},params={"invoice":str(invoice)})
                raw=r.json()
                if r.status_code >= 400: return None
            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            merged={**d,**raw}
            return {"invoice_id":str(merged.get("invoice_id") or invoice),"status":str(merged.get("status") or merged.get("payment_status") or "").lower(),"amount":int(merged.get("final_amount") or merged.get("amount") or 0)}
        except Exception:
            log.exception("BayarGG check payment failed")
            return None
