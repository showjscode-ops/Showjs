import httpx,re,unicodedata
from config import BAYARGG_API_KEY,BAYARGG_BASE_URL
def clean_name(name):
    name=unicodedata.normalize("NFKC",name or "Customer").encode("ascii","ignore").decode("ascii"); name=re.sub(r"[^A-Za-z0-9 .,_-]","",name); return re.sub(r"\s+"," ",name).strip()[:50] or "Customer"
class BayarGG:
 @staticmethod
 async def create_payment(amount,description,callback_url=None,customer_name=None):
    if not BAYARGG_API_KEY:return None
    payload={"amount":int(amount),"description":description,"payment_url":"https://www.bayar.gg/pay","payment_method":"qris","customer_name":clean_name(customer_name or "Customer")}
    if callback_url: payload["callback_url"]=callback_url
    try:
      async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(f"{BAYARGG_BASE_URL}/create-payment.php",headers={"X-API-Key":BAYARGG_API_KEY,"Content-Type":"application/json"},json=payload); r.raise_for_status(); raw=r.json()
      if not raw.get("success"): return None
      d=raw.get("data",raw); inv=d.get("invoice_id") or d.get("id") or d.get("invoice"); qr=d.get("qris_string") or d.get("qris") or d.get("qr_string") or d.get("qr")
      if not inv or not qr:return None
      return {"invoice_id":str(inv),"qr_string":qr,"payment_url":d.get("payment_url"),"amount":int(d.get("final_amount") or d.get("amount") or amount)}
    except Exception:return None
 @staticmethod
 async def check_payment(invoice):
    if not BAYARGG_API_KEY:return None
    try:
      async with httpx.AsyncClient(timeout=30) as c:
        r=await c.get(f"{BAYARGG_BASE_URL}/check-payment.php",headers={"X-API-Key":BAYARGG_API_KEY},params={"invoice":invoice}); r.raise_for_status(); raw=r.json()
      if not raw.get("success"):return None
      d=raw.get("data",raw); return {"invoice_id":invoice,"status":str(d.get("status") or d.get("payment_status") or "").lower(),"amount":int(d.get("amount") or 0)}
    except Exception:return None
