import uuid,base64,binascii
from io import BytesIO
import qrcode
from aiogram.types import BufferedInputFile
from database import get_pool
from config import BAYARGG_WEBHOOK_URL
from utils.bayargg import BayarGG
from utils.cashi import Cashi
from utils.notify_channel import notify

def qr_bytes(value):
    value=str(value or "")
    if value.startswith("data:image/"):
        try:return base64.b64decode(value.split(',',1)[1],validate=True)
        except (ValueError,binascii.Error):return None
    buf=BytesIO(); qrcode.make(value).save(buf,format="PNG"); return buf.getvalue()
async def enabled(provider):
    p=await get_pool(); return str(await p.fetchval("SELECT value FROM settings WHERE key=$1",f"payment_{provider}_enabled") or "off").lower() in {"on","1","true","yes"}
async def create_purchase(uid,typ,qty,amount,provider,name):
    if not await enabled(provider): return None,"disabled"
    order=f"{provider.upper()}-{uuid.uuid4().hex}"
    if provider=="bayargg": r=await BayarGG.create_payment(amount,f"{typ}:{qty}",BAYARGG_WEBHOOK_URL,name)
    else: r=await Cashi.create_payment(amount,f"{typ}:{qty}",name)
    if not r:return None,"provider_error"
    p=await get_pool(); await p.execute("INSERT INTO purchases(user_id,purchase_type,quantity,amount,provider,order_id,invoice_id) VALUES($1,$2,$3,$4,$5,$6,$7)",uid,typ,qty,amount,provider,order,r["invoice_id"])
    return r,"ok"
async def finalize_purchase(invoice,status_amount=None):
    p=await get_pool()
    async with p.acquire() as c:
      async with c.transaction():
        row=await c.fetchrow("SELECT * FROM purchases WHERE invoice_id=$1 FOR UPDATE",str(invoice))
        if not row:return False
        if row["status"]=="paid":return True
        if status_amount is not None and int(status_amount)!=int(row["amount"]): return False
        await c.execute("UPDATE purchases SET status='paid',paid_at=NOW() WHERE id=$1",row["id"])
        if row["purchase_type"]=="points":
            await c.execute("UPDATE users SET points=points+$1 WHERE user_id=$2",row["quantity"],row["user_id"])
            text=f"💰 PEMBELIAN POIN\n\n🆔 ID: {row['user_id']}\n🪙 Paket: {row['quantity']:g} Poin\n💵 Harga: Rp{int(row['amount']):,}\n💳 Status: PAID".replace(',','.')
        elif row["purchase_type"]=="stars":
            await c.execute("UPDATE users SET stars=stars+$1 WHERE user_id=$2",row["quantity"],row["user_id"])
            text=f"⭐ PEMBELIAN STAR\n\n🆔 ID: {row['user_id']}\n⭐ Paket: {row['quantity']:g} Star\n💵 Harga: Rp{int(row['amount']):,}\n💳 Status: PAID".replace(',','.')
        else:
            from datetime import timedelta
            await c.execute("UPDATE users SET vip=TRUE,vip_until=NOW()+($1 || ' days')::interval WHERE user_id=$2",int(row["quantity"]),row["user_id"])
            text=f"💎 PEMBELIAN VIP\n\n🆔 ID: {row['user_id']}\n💎 Paket: {row['quantity']:g} Hari\n💵 Harga: Rp{int(row['amount']):,}\n💳 Status: PAID".replace(',','.')
    try:
        from bot import bot
        await notify(bot,text)
        try:
            await bot.send_message(int(row["user_id"]), "✅ Pembayaran berhasil. Saldo/paket sudah masuk otomatis.")
        except Exception:
            pass
    except Exception:
        pass
    return text
