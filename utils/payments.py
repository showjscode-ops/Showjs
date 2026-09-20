
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
    metadata=dict(metadata or {})
    p=await get_pool()

    # Reuse an existing pending QR for the same purchase while it is still valid.
    # This prevents duplicate invoices when a user presses Buy again before expiry.
    candidates=await p.fetch("""
        SELECT * FROM purchases
        WHERE user_id=$1 AND purchase_type=$2 AND provider=$3 AND amount=$4
          AND status='pending'
        ORDER BY id DESC LIMIT 5
    """,uid,typ,provider,amount)
    for old in candidates:
        oldmeta=old["metadata"] or {}
        if metadata.get("code") and str(oldmeta.get("code") or "") != str(metadata.get("code")):
            continue
        inv=old["invoice_id"]
        try:
            from utils.bayargg import BayarGG
            from utils.cashi import Cashi
            chk=await (BayarGG.check_payment(inv) if provider=="bayargg" else Cashi.check_payment(inv))
            status=str((chk or {}).get("status") or "").lower()
            if status in {"paid","success","completed","settled"}:
                await finalize_purchase(inv,(chk or {}).get("amount") or None)
                continue
            if status in {"expired","cancelled","canceled","failed"}:
                await p.execute("UPDATE purchases SET status=$1 WHERE id=$2 AND status='pending'",status,old["id"])
                continue
        except Exception:
            # If the provider cannot be checked right now, do not create a
            # duplicate invoice if we still have the stored QR.
            pass
        qr=oldmeta.get("qr_string")
        if qr:
            return {
                "invoice_id":str(inv),
                "qr_string":qr,
                "payment_url":oldmeta.get("payment_url"),
                "amount":int(oldmeta.get("final_amount") or amount),
                "expires_at":oldmeta.get("expires_at"),
                "reused":True,
            },"ok"

    order=f"{provider.upper()}-{uuid.uuid4().hex}"
    desc=f"{typ}:{qty}"
    if metadata.get("code"): desc=f"file:{metadata['code']}"
    r=await (BayarGG.create_payment(amount,desc,BAYARGG_WEBHOOK_URL,name) if provider=="bayargg" else Cashi.create_payment(amount,desc,name))
    if not r:return None,"provider_error"

    metadata.update({
        "qr_string": r.get("qr_string"),
        "payment_url": r.get("payment_url"),
        "final_amount": r.get("amount") or amount,
        "expires_at": r.get("expires_at"),
    })
    await p.execute("""INSERT INTO purchases(user_id,purchase_type,quantity,amount,provider,order_id,invoice_id,metadata,expires_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
    uid,typ,qty,amount,provider,order,r["invoice_id"],json.dumps(metadata),
    r.get("expires_at"))
    return r,"ok"


async def _transaction_post(bot, typ, uid, qty, amount, provider, meta=None):
    try:
        from config import TRANSACTION_CHAT_ID, TRANSACTION_CHANNEL_URL
        if not TRANSACTION_CHAT_ID:
            return
        label={"points":"🪙 Buy Poin","stars":"⭐ Buy Star","vip":"💎 Buy VIP","creator":"👑 Buy Creator"}.get(typ,typ)
        await bot.send_message(
            TRANSACTION_CHAT_ID,
            f"💳 <b>TRANSACTION SUCCESS</b>\n\n"
            f"👤 User ID: <code>{uid}</code>\n"
            f"📦 Type: <b>{label}</b>\n"
            f"🔢 Quantity: <b>{qty:g}</b>\n"
            f"💰 Amount: <b>Rp{int(amount):,}</b>\n"
            f"🏦 Provider: <b>{provider.upper()}</b>\n"
            f"🔗 Channel: {TRANSACTION_CHANNEL_URL}".replace(',','.'),
            parse_mode="HTML"
        )
    except Exception:
        pass

async def finalize_purchase(invoice,status_amount=None):
    p=await get_pool()
    async with p.acquire() as c:
      async with c.transaction():
        row=await c.fetchrow("SELECT * FROM purchases WHERE invoice_id=$1 FOR UPDATE",str(invoice))
        if not row:return False
        if row["status"]=="paid":return True
        if row["status"]!="pending":return False
        if status_amount is not None and int(status_amount)!=int(row["amount"]): return False
        await c.execute("UPDATE purchases SET status='paid',paid_at=NOW() WHERE id=$1",row["id"])
        typ=row["purchase_type"]; uid=row["user_id"]; qty=row["quantity"]; meta=row["metadata"] or {}
        if typ=="points":
            await c.execute("UPDATE users SET points=points+$1 WHERE user_id=$2",qty,uid)
        elif typ=="stars":
            await c.execute("UPDATE users SET stars=stars+$1 WHERE user_id=$2",qty,uid)
        elif typ=="vip":
            await c.execute("UPDATE users SET vip=TRUE,vip_until=GREATEST(COALESCE(vip_until,NOW()),NOW())+($1||' days')::interval WHERE user_id=$2",int(qty),uid)
        elif typ=="creator":
            # Payment success records the creator registration. Admin can
            # complete approval/evaluation separately.
            await c.execute("UPDATE users SET creator_status=CASE WHEN creator_status='approved' THEN creator_status ELSE 'pending' END WHERE user_id=$1",uid)
        elif typ=="deposit":
            await c.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2",row["amount"],uid)
        elif typ=="file":
            code=str(meta.get("code") or "")
            f=await c.fetchrow("SELECT owner_id,price_idr FROM files WHERE code=$1 AND active=TRUE FOR UPDATE",code)
            if not f: return False
            price=int(f["price_idr"] or row["amount"])
            if price!=int(row["amount"]): return False
            creator_id=int(f["owner_id"]); income=price*0.70
            await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)
            await c.execute("UPDATE users SET total_unlocks=total_unlocks+1 WHERE user_id=$2",uid)
            if creator_id!=uid:
                await c.execute("UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1,points=points+1 WHERE user_id=$2",income,creator_id)
            await c.execute("""INSERT INTO unlock_transactions(user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at)
            VALUES($1,$2,$3,'qr',$4,1,$5,NOW()+INTERVAL '24 hours')""",uid,creator_id,code,price,income)

    try:
        from bot import bot
        from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
        await _transaction_post(bot,typ,int(uid),float(qty),int(row["amount"]),str(row["provider"]),meta)
        if typ=='file':
            await bot.send_message(int(uid),f'✅ <b>Payment successful</b>\n\n🔑 Code: <code>{meta.get("code")}</code>\n📥 Tekan judul/code untuk membuka media.',parse_mode='HTML')
        elif typ=='deposit':
            bal=await p.fetchval("SELECT balance FROM users WHERE user_id=$1",uid)
            await bot.send_message(int(uid),f'✅ Deposit berhasil.\n💰 Saldo sekarang: <b>Rp{int(bal or 0):,}</b>'.replace(',','.'),parse_mode='HTML')
        elif typ=='creator':
            await bot.send_message(int(uid),'✅ Pembayaran Creator berhasil.\n👑 Pendaftaran Creator kamu sudah tercatat dan menunggu proses verifikasi admin.',parse_mode='HTML')
        else:
            await bot.send_message(int(uid),'✅ Pembayaran berhasil. Saldo/paket sudah masuk otomatis.')
    except Exception:
        pass
    return True
