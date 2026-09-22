import logging
import uuid
from datetime import datetime, timezone
import httpx
from config import (
    CASHI_API_KEY, CASHI_BASE_URL, CASHI_PAYMENT_CHANNEL,
    CASHI_MIN_AMOUNT, CASHI_MAX_AMOUNT
)
logger = logging.getLogger(__name__)

def _unwrap(raw):
    if not isinstance(raw, dict):
        return {}
    d = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    if isinstance(raw.get("result"), dict):
        d = {**d, **raw["result"]}
    return {**d, **raw}

def _status(v):
    return str(v or "").strip().lower().replace("-", "_").replace(" ", "_")

def _amount(v, default=0):
    try:
        if v is None or v == "":
            return int(default)
        return int(float(v))
    except (TypeError, ValueError):
        return int(default)

def _parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None

class Cashi:
    @staticmethod
    async def create_payment(amount, description, customer_name="Customer"):
        amount=_amount(amount)
        if not CASHI_API_KEY or not (int(CASHI_MIN_AMOUNT) <= amount <= int(CASHI_MAX_AMOUNT)):
            return None
        order=f"FILE-{uuid.uuid4().hex[:16]}"
        body={
            "amount":amount,
            "order_id":order,
            "kode_channel":CASHI_PAYMENT_CHANNEL,
            "description":str(description or "")[:200],
            "customer_name":str(customer_name or "Customer")[:100],
        }
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.post(
                    f"{CASHI_BASE_URL}/api/create-order",
                    json=body,
                    headers={"x-api-key":CASHI_API_KEY,"Content-Type":"application/json","Accept":"application/json"},
                )
                raw=r.json()
            logger.info("CASHI CREATE HTTP %s | %s",r.status_code,raw)
            if r.status_code >= 400 or (isinstance(raw,dict) and raw.get("success") is False):
                return None
            d=_unwrap(raw)
            oid=str(d.get("orderId") or d.get("order_id") or d.get("invoice_id") or order)
            qr=d.get("qrUrl") or d.get("qr_url") or d.get("qris") or d.get("qr_string") or d.get("qr")
            checkout=d.get("checkout_url") or d.get("payment_url")
            if isinstance(qr,str) and qr.startswith("http") and not checkout:
                checkout=qr
            return {
                "invoice_id":oid,
                "order_id":oid,
                "qr_string":qr if isinstance(qr,str) and not qr.startswith("http") else None,
                "qr_image":qr if isinstance(qr,str) else None,
                "payment_url":checkout,
                "amount":_amount(d.get("amount"),amount),
                "final_amount":_amount(d.get("final_amount"),_amount(d.get("amount"),amount)),
                "expires_at":_parse_dt(d.get("expires_at") or d.get("expired_at")),
                "status":_status(d.get("status")),
            }
        except Exception:
            logger.exception("CASHI create payment failed")
            return None

    @staticmethod
    async def check_payment(order_id):
        if not CASHI_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r=await c.get(
                    f"{CASHI_BASE_URL}/api/check-status/{order_id}",
                    headers={"x-api-key":CASHI_API_KEY,"Accept":"application/json"},
                )
                raw=r.json()
            if r.status_code >= 400:
                logger.error("CASHI CHECK HTTP %s | %s",r.status_code,raw)
                return None
            d=_unwrap(raw)
            status=_status(
                d.get("status") or d.get("payment_status") or
                d.get("paymentStatus") or d.get("transaction_status") or
                d.get("event")
            )
            amount=_amount(d.get("amount"),0)
            if not amount:
                amount=_amount(d.get("paid_amount"),0)
            if not amount:
                amount=_amount(d.get("final_amount"),0)
            return {
                "invoice_id":str(d.get("order_id") or d.get("orderId") or d.get("invoice_id") or order_id),
                "status":status,
                "amount":amount,
                "final_amount":amount,
                "paid_at":d.get("paid_at"),
                "raw":d,
            }
        except Exception:
            logger.exception("CASHI check payment failed")
            return None
