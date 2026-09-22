import hashlib,hmac,json,logging
from fastapi import APIRouter,Request
from fastapi.responses import PlainTextResponse
from config import CASHI_SECRET_KEY
from utils.payments import finalize_purchase

log=logging.getLogger(__name__)
router=APIRouter(prefix="/cashi",tags=["CASHI"])
PAID={"paid","success","completed","settled","settled_payment","payment_settled"}

def _valid(body,sig):
    secret=str(CASHI_SECRET_KEY or "").strip()
    sig=str(sig or "").strip().lower()
    if not secret or not sig:return False
    if sig.startswith("sha256="):sig=sig[7:].strip()
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,sig)

def _data(d):
    x=d.get("data")
    return x if isinstance(x,dict) else d

async def _handle(request:Request):
    body=await request.body()
    sig=(request.headers.get("x-gateway-signature") or
         request.headers.get("x-cashi-signature") or
         request.headers.get("x-webhook-signature") or "")
    # If a secret is configured, signature is mandatory. This keeps existing
    # deployments working when they have no Cashi signing secret configured.
    if CASHI_SECRET_KEY and not _valid(body,sig):
        return PlainTextResponse("Invalid signature",status_code=401)
    try:d=json.loads(body.decode())
    except Exception:return PlainTextResponse("Invalid JSON",status_code=400)
    if not isinstance(d,dict):return PlainTextResponse("Invalid payload",status_code=400)
    x=_data(d)
    event=str(x.get("event") or d.get("event") or "").strip().lower()
    status=str(x.get("status") or d.get("status") or x.get("payment_status") or "").strip().lower()
    inv=str(x.get("order_id") or d.get("order_id") or x.get("orderId") or x.get("invoice_id") or "").strip()
    if inv.upper().startswith("TEST-"):
        return PlainTextResponse("Test connection successful",status_code=200)
    if event and event not in PAID and status not in PAID:
        return PlainTextResponse("OK",status_code=200)
    if status not in PAID and event not in PAID:
        return PlainTextResponse("OK",status_code=200)
    if not inv:return PlainTextResponse("Missing order_id",status_code=400)
    amount=x.get("amount") or x.get("paid_amount") or x.get("final_amount")
    try: amount=int(float(amount)) if amount is not None else None
    except (TypeError,ValueError):return PlainTextResponse("Invalid amount",status_code=400)
    ok=await finalize_purchase(inv,amount)
    if not ok:
        # A second webhook may race with the worker. If already paid, ACK it.
        from database import fetchrow
        row=await fetchrow("SELECT status FROM purchases WHERE invoice_id=$1",inv)
        if row and str(row["status"]).lower()=="paid":
            return PlainTextResponse("OK",status_code=200)
        log.error("CASHI settlement failed invoice=%s",inv)
        return PlainTextResponse("Processing failed",status_code=500)
    return PlainTextResponse("OK",status_code=200)

@router.get("/webhook")
async def health():return PlainTextResponse("OK",status_code=200)
@router.post("/webhook")
async def webhook(request:Request):return await _handle(request)

# Compatibility aliases.
@router.get("/api/webhook/cashi")
async def health_alias():return PlainTextResponse("OK",status_code=200)
@router.post("/api/webhook/cashi")
async def webhook_alias(request:Request):return await _handle(request)
@router.get("/webhook/cashi")
async def health_alias2():return PlainTextResponse("OK",status_code=200)
@router.post("/webhook/cashi")
async def webhook_alias2(request:Request):return await _handle(request)
