import httpx,re,unicodedata,logging
from config import BAYARGG_API_KEY,BAYARGG_BASE_URL,BAYARGG_WEBHOOK_URL

log=logging.getLogger(__name__)

def clean_name(name):
    name=unicodedata.normalize("NFKC",name or "Customer").encode("ascii","ignore").decode("ascii")
    name=re.sub(r"[^A-Za-z0-9 .,_-]","",name)
    return re.sub(r"\s+"," ",name).strip()[:50] or "Customer"

class BayarGG:
    PAYMENT_METHOD="qris"
    PAYMENT_URL="https://www.bayar.gg/pay"

    @staticmethod
    async def create_payment(amount,description,callback_url=None,customer_name=None):
        if not BAYARGG_API_KEY:
            log.error("BayarGG API key is not configured")
            return None

        amount=int(amount)
        if amount < 5000 or amount > 500000:
            log.error("BayarGG QRIS amount outside allowed range: %s", amount)
            return None

        # BayarGG requires payment_url even when the merchant does not show
        # a checkout/open button to the Telegram user.
        payload={
            "amount":amount,
            "description":str(description)[:200],
            "customer_name":clean_name(customer_name or "Customer"),
            "payment_url":BayarGG.PAYMENT_URL,
            "payment_method":BayarGG.PAYMENT_METHOD,
        }
        cb=callback_url or BAYARGG_WEBHOOK_URL
        if cb:
            payload["callback_url"]=str(cb)

        try:
            log.info(
                "BayarGG create: amount=%s method=%s payment_url=%s",
                payload["amount"],payload["payment_method"],payload["payment_url"]
            )
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.post(
                    f"{BAYARGG_BASE_URL}/create-payment.php",
                    headers={"X-API-Key":BAYARGG_API_KEY,"Content-Type":"application/json"},
                    json=payload,
                )
                try:
                    raw=r.json()
                except Exception:
                    raw={"raw":r.text}

            if r.status_code >= 400:
                log.error("BayarGG create HTTP %s: %s",r.status_code,raw)
                return None
            if not isinstance(raw,dict) or not raw.get("success",False):
                log.error("BayarGG create rejected: %s",raw)
                return None

            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            merged={**d,**raw}
            inv=merged.get("invoice_id") or merged.get("invoice") or merged.get("id")
            qr=merged.get("qris_string") or merged.get("qris") or merged.get("qr_string")
            checkout=merged.get("payment_url") or BayarGG.PAYMENT_URL
            final_amount=merged.get("final_amount") or merged.get("amount") or amount

            if not inv:
                log.error("BayarGG create succeeded but invoice_id missing: %s",raw)
                return None

            return {
                "invoice_id":str(inv),
                "qr_string":qr if isinstance(qr,str) else None,
                "payment_url":str(checkout),
                "amount":int(final_amount),
            }
        except Exception:
            log.exception("BayarGG create payment failed")
            return None

    @staticmethod
    async def check_payment(invoice):
        if not BAYARGG_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.get(
                    f"{BAYARGG_BASE_URL}/check-payment.php",
                    headers={"X-API-Key":BAYARGG_API_KEY},
                    params={"invoice":str(invoice)},
                )
                try:
                    raw=r.json()
                except Exception:
                    raw={"raw":r.text}

            if r.status_code >= 400:
                log.error("BayarGG check HTTP %s: %s",r.status_code,raw)
                return None

            d=raw.get("data") if isinstance(raw.get("data"),dict) else {}
            merged={**d,**raw}
            status=str(
                merged.get("status")
                or merged.get("payment_status")
                or ""
            ).lower().strip()

            amount=merged.get("final_amount")
            if amount is None:
                amount=merged.get("amount")
            try:
                amount=int(amount or 0)
            except Exception:
                amount=0

            return {
                "invoice_id":str(merged.get("invoice_id") or invoice),
                "status":status,
                "amount":amount,
                "final_amount":amount,
                "payment_method":merged.get("payment_method"),
                "paid_at":merged.get("paid_at"),
            }
        except Exception:
            log.exception("BayarGG check payment failed")
            return None
