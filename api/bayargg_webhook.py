import hmac,hashlib,json,logging
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from config import BAYARGG_WEBHOOK_SECRET,BAYARGG_SECRET
from utils.payments import finalize_purchase
from database import fetchrow

log=logging.getLogger(__name__)
router=APIRouter(prefix="/bayargg",tags=["BayarGG"])
PAID={"paid","success","completed","settled"}

def _secret():
    return str(BAYARGG_WEBHOOK_SECRET or BAYARGG_SECRET or "").strip()

def _valid(body,sig):
    secret=_secret()
    if not secret:return True
    sig=str(sig or "").strip()
    if sig.lower().startswith("sha256="):sig=sig[7:].strip()
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,sig)

def _data(d):
    x=d.get("data")
    return x if isinstance(x,dict) else d

@router.get("/webhook")
async def health():return {"success":True,"message":"OK"}

@router.post("/webhook")
async def webhook(request:Request):
    body=await request.body()
    sig=(request.headers.get("X-Webhook-Signature") or
         request.headers.get("X-Callback-Signature") or
         request.headers.get("X-Signature") or "")
    if not _valid(body,sig):
        return JSONResponse({"success":False,"message":"invalid signature"},status_code=401)
    try:d=json.loads(body.decode())
    except Exception:return JSONResponse({"success":False,"message":"invalid json"},status_code=400)
    if not isinstance(d,dict):return JSONResponse({"success":False,"message":"invalid payload"},status_code=400)
    x=_data(d)
    event=str(x.get("event") or d.get("event") or x.get("type") or d.get("type") or "").lower()
    status=str(x.get("status") or d.get("status") or x.get("payment_status") or d.get("payment_status") or "").lower()
    if status not in PAID and event not in {"payment.paid","paid","payment.success","payment.completed","settled"}:
        return {"success":True,"message":"ignored"}
    inv=str(x.get("invoice_id") or x.get("invoice") or x.get("id") or d.get("invoice_id") or request.headers.get("X-Invoice-ID") or "").strip()
    if not inv:return JSONResponse({"success":False,"message":"missing invoice"},status_code=400)
    amount=x.get("final_amount")
    if amount is None:amount=x.get("amount")
    try:amount=int(float(amount)) if amount is not None else None
    except (TypeError,ValueError):return JSONResponse({"success":False,"message":"invalid amount"},status_code=400)
    ok=await finalize_purchase(inv,amount)
    if not ok:
        row=await fetchrow("SELECT status FROM purchases WHERE invoice_id=$1",inv)
        if row and str(row["status"]).lower()=="paid":
            return {"success":True,"message":"already processed"}
        log.error("BAYARGG settlement failed invoice=%s",inv)
        return JSONResponse({"success":False,"message":"processing failed"},status_code=500)
    return {"success":True,"message":"processed"}
