
import uuid,base64,binascii,json
from io import BytesIO
import qrcode
from aiogram.types import BufferedInputFile
from database import get_pool
from config import BAYARGG_WEBHOOK_URL
from utils.bayargg import BayarGG
from utils.cashi import Cashi

def qr_bytes(value):
    value=str(value or "")
    if value.startswith("data:image/"):
        try:return base64.b64decode(value.split(',',1)[1],validate=True)
        except (ValueError,binascii.Error):return None
    buf=BytesIO(); qrcode.make(value).save(buf,format="PNG"); return buf.getvalue()

async def enabled(provider):
    """Return the single canonical payment toggle used by both admin and checkout.

    Aliases such as balance_bayargg were the cause of the old mismatch: the
    admin panel changed payment_bayargg_enabled while checkout sometimes
    looked for payment_balance_bayargg_enabled. Keep aliases only as input
    compatibility; NEVER create/read a second setting key.
    """
    aliases = {
        "balance_bayargg": "bayargg",
        "balance_cashi": "cashi",
        "payment_bayargg": "bayargg",
        "payment_cashi": "cashi",
        "payment_manual": "manual",
        "payment_balance": "balance",
    }
    provider = aliases.get(str(provider).lower(), str(provider).lower())
    key_map = {
        "bayargg": "payment_bayargg_enabled",
        "cashi": "payment_cashi_enabled",
        "manual": "payment_manual_enabled",
        "balance": "payment_balance_enabled",
    }
    key = key_map.get(provider)
    if not key:
        return False
    p = await get_pool()
    value = await p.fetchval("SELECT value FROM settings WHERE key=$1", key)
    return str(value or "off").strip().lower() in {"on", "1", "true", "yes", "enabled"}

async def create_purchase(uid,typ,qty,amount,provider,name,metadata=None):
    provider=str(provider).lower().strip()
    amount=int(amount)
    if not await enabled(provider): return None,"disabled"
    if provider=="bayargg" and not (5000 <= amount <= 500000):
        return None,"invalid_amount"
    order=f"{provider.upper()}-{uuid.uuid4().hex}"
    desc=f"{typ}:{qty}"
    if metadata and metadata.get("code"): desc=f"file:{metadata['code']}"
    r=await (BayarGG.create_payment(amount,desc,BAYARGG_WEBHOOK_URL,name) if provider=="bayargg" else Cashi.create_payment(amount,desc,name))
    if not r:return None,"provider_error"
    p=await get_pool()
    await p.execute("""INSERT INTO purchases(user_id,purchase_type,quantity,amount,provider,order_id,invoice_id,metadata)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb)""",uid,typ,qty,amount,provider,order,r["invoice_id"],json.dumps(metadata or {}))
    return r,"ok"

async def finalize_purchase(invoice,status_amount=None):
    p=await get_pool()
    async with p.acquire() as c:
      async with c.transaction():
        row=await c.fetchrow("SELECT * FROM purchases WHERE invoice_id=$1 FOR UPDATE",str(invoice))
        if not row:return False
        if row["status"]=="paid":return True
        if status_amount is not None and int(status_amount)!=int(row["amount"]):return False
        await c.execute("UPDATE purchases SET status='paid',paid_at=NOW() WHERE id=$1",row["id"])
        typ=row["purchase_type"]; uid=row["user_id"]; qty=row["quantity"]; meta=row["metadata"] or {}
        if typ=="points":
            await c.execute("UPDATE users SET points=points+$1 WHERE user_id=$2",qty,uid)
        elif typ=="stars":
            await c.execute("UPDATE users SET stars=stars+$1 WHERE user_id=$2",qty,uid)
        elif typ=="vip":
            await c.execute("UPDATE users SET vip=TRUE,vip_until=GREATEST(COALESCE(vip_until,NOW()),NOW())+($1||' days')::interval WHERE user_id=$2",int(qty),uid)
        elif typ=="deposit":
            await c.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2",row["amount"],uid)
        elif typ=="file":
            code=str(meta.get("code") or "")
            f=await c.fetchrow("SELECT owner_id,price_idr FROM files WHERE code=$1 AND active=TRUE FOR UPDATE",code)
            if not f: return False
            price=int(f["price_idr"] or row["amount"])
            if price!=int(row["amount"]): return False
            creator_id=int(f["owner_id"]); income=price*0.20
            await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)
            await c.execute("UPDATE users SET total_unlocks=total_unlocks+1 WHERE user_id=$2",uid)
            if creator_id!=uid:
                await c.execute("UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1,points=points+1 WHERE user_id=$2",income,creator_id)
            await c.execute("""INSERT INTO unlock_transactions(user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at)
            VALUES($1,$2,$3,'qr',$4,1,$5,NOW()+INTERVAL '100 years')""",uid,creator_id,code,price,income)
    try:
        from bot import bot
        from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
        if typ=='file':
            await bot.send_message(int(uid),f'✅ <b>Payment successful</b>\n\n🔑 Code: <code>{meta.get("code")}</code>\n📥 Tekan tombol untuk membuka media.',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📥 Buka Code',callback_data=f'getcode:{meta.get("code")}')]]))
        elif typ=='deposit':
            bal=await p.fetchval("SELECT balance FROM users WHERE user_id=$1",uid)
            await bot.send_message(int(uid),f'✅ Deposit berhasil.\n💰 Saldo sekarang: <b>Rp{int(bal or 0):,}</b>'.replace(',','.'),parse_mode='HTML')
        else:
            await bot.send_message(int(uid),'✅ Pembayaran berhasil. Saldo/paket sudah masuk otomatis.')
    except Exception:
        pass
    return True
