import httpx,re,unicodedata,logging
from config import BAYARGG_API_KEY,BAYARGG_BASE_URL,BAYARGG_WEBHOOK_URL
log=logging.getLogger(__name__)

def clean_name(name):
    name=unicodedata.normalize("NFKC",str(name or "Customer")).encode("ascii","ignore").decode("ascii")
    name=re.sub(r"[^A-Za-z0-9 .,_-]","",name)
    return re.sub(r"\s+"," ",name).strip()[:50] or "Customer"

def _unwrap(raw):
    if not isinstance(raw,dict): return {}
    d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
    if isinstance(raw.get("result"),dict): d={**d,**raw["result"]}
    return {**d,**raw}

def _status(v):
    return str(v or "").strip().lower().replace("-","_").replace(" ","_")

def _amount(v,default=0):
    try:return int(float(v if v not in (None,"") else default))
    except (TypeError,ValueError):return int(default)

class BayarGG:
    PAYMENT_METHOD="qris"
    PAYMENT_URL="https://www.bayar.gg/pay"

    @staticmethod
    async def create_payment(amount,description,callback_url=None,customer_name=None):
        amount=_amount(amount)
        if not BAYARGG_API_KEY or amount<5000 or amount>500000:
            return None
        payload={
            "amount":amount,
            "description":str(description or "")[:200],
            "customer_name":clean_name(customer_name),
            "payment_url":BayarGG.PAYMENT_URL,
            "payment_method":BayarGG.PAYMENT_METHOD,
            "callback_url":str(callback_url or BAYARGG_WEBHOOK_URL),
        }
        payload={k:v for k,v in payload.items() if v not in (None,"")}
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.post(
                    f"{BAYARGG_BASE_URL}/create-payment.php",
                    headers={"X-API-Key":BAYARGG_API_KEY,"Content-Type":"application/json","Accept":"application/json"},
                    json=payload,
                )
                try: raw=r.json()
                except Exception: raw={"raw":r.text}
            log.info("BAYARGG CREATE HTTP %s | %s",r.status_code,raw)
            if r.status_code>=400 or not isinstance(raw,dict) or raw.get("success") is False:
                return None
            d=_unwrap(raw)
            inv=d.get("invoice_id") or d.get("invoice") or d.get("id")
            qr=d.get("qris_string") or d.get("qris") or d.get("qr_string") or d.get("qr")
            if not inv or not qr:
                log.error("BAYARGG create missing invoice/QR: %s",raw)
                return None
            final=_amount(d.get("final_amount"),_amount(d.get("amount"),amount))
            return {"invoice_id":str(inv),"qr_string":qr if isinstance(qr,str) else None,
                    "payment_url":d.get("payment_url") or BayarGG.PAYMENT_URL,
                    "amount":final,"final_amount":final,"expires_at":d.get("expires_at"),
                    "status":_status(d.get("status"))}
        except Exception:
            log.exception("BAYARGG create payment failed")
            return None

    @staticmethod
    async def check_payment(invoice):
        if not BAYARGG_API_KEY:return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.get(
                    f"{BAYARGG_BASE_URL}/check-payment.php",
                    headers={"X-API-Key":BAYARGG_API_KEY,"Accept":"application/json"},
                    params={"invoice":str(invoice)},
                )
                try: raw=r.json()
                except Exception: raw={"raw":r.text}
            if r.status_code>=400:return None
            d=_unwrap(raw)
            amount=_amount(d.get("final_amount"),_amount(d.get("amount"),0))
            return {"invoice_id":str(d.get("invoice_id") or d.get("invoice") or invoice),
                    "status":_status(d.get("status") or d.get("payment_status")),
                    "amount":amount,"final_amount":amount,
                    "payment_method":d.get("payment_method"),"paid_at":d.get("paid_at"),"raw":d}
        except Exception:
            log.exception("BAYARGG check payment failed")
            return None
