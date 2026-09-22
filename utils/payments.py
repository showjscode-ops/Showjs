import uuid,base64,binascii,json,logging
from io import BytesIO
from decimal import Decimal
from datetime import datetime, timezone
import qrcode
from database import get_pool
from config import BAYARGG_WEBHOOK_URL
from utils.bayargg import BayarGG
from utils.cashi import Cashi

log=logging.getLogger(__name__)

PAID_STATUSES={"paid","success","completed","settled"}
FAILED_STATUSES={"expired","cancelled","canceled","failed"}

def qr_bytes(value):
    value=str(value or "")
    if not value:
        return None
    if value.startswith("data:image/"):
        try:return base64.b64decode(value.split(",",1)[1],validate=True)
        except (ValueError,binascii.Error):return None
    # Some providers return a QR payload rather than an image. Generate a
    # PNG from the payload. HTTP image URLs are left out here because the
    # Telegram handler can still display the payment URL as a fallback.
    if value.startswith("http://") or value.startswith("https://"):
        return None
    buf=BytesIO()
    qrcode.make(value).save(buf,format="PNG")
    return buf.getvalue()

def _parse_dt(v):
    if not v:return None
    if isinstance(v,datetime):return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None

def _norm_status(v):
    return str(v or "").strip().lower().replace("-","_").replace(" ","_")

async def enabled(provider):
    aliases={"balance_bayargg":"bayargg","balance_cashi":"cashi",
             "payment_bayargg":"bayargg","payment_cashi":"cashi",
             "payment_manual":"manual","payment_balance":"balance"}
    provider=aliases.get(str(provider).lower(),str(provider).lower())
    key={"bayargg":"payment_bayargg_enabled","cashi":"payment_cashi_enabled",
         "manual":"payment_manual_enabled","balance":"payment_balance_enabled"}.get(provider)
    if not key:return False
    p=await get_pool()
    value=await p.fetchval("SELECT value FROM settings WHERE key=$1",key)
    return str(value or "off").strip().lower() in {"on","1","true","yes","enabled"}

async def create_purchase(uid,typ,qty,amount,provider,name,metadata=None):
    provider=str(provider).lower().strip()
    amount=int(amount)
    if not await enabled(provider):return None,"disabled"
    if provider=="bayargg" and not 5000<=amount<=500000:return None,"invalid_amount"
    if provider=="cashi":
        try:
            from config import CASHI_MIN_AMOUNT,CASHI_MAX_AMOUNT
            if not int(CASHI_MIN_AMOUNT)<=amount<=int(CASHI_MAX_AMOUNT):return None,"invalid_amount"
        except Exception:pass

    metadata=dict(metadata or {})
    p=await get_pool()

    # Reuse a still-pending invoice. This prevents duplicate provider orders
    # when the user taps Buy/Cek repeatedly.
    candidates=await p.fetch("""
        SELECT * FROM purchases
        WHERE user_id=$1 AND purchase_type=$2 AND provider=$3 AND amount=$4
          AND status='pending'
        ORDER BY id DESC LIMIT 5
    """,uid,typ,provider,amount)
    for old in candidates:
        oldmeta=old["metadata"] or {}
        if metadata.get("code") and str(oldmeta.get("code") or "")!=str(metadata.get("code") or ""):
            continue
        inv=str(old["invoice_id"] or "")
        if inv:
            try:
                chk=await (BayarGG.check_payment(inv) if provider=="bayargg" else Cashi.check_payment(inv))
                st=_norm_status((chk or {}).get("status"))
                if st in PAID_STATUSES:
                    if await finalize_purchase(inv,(chk or {}).get("amount") or None):
                        continue
                if st in FAILED_STATUSES:
                    await p.execute("UPDATE purchases SET status=$1 WHERE id=$2 AND status='pending'",st,old["id"])
                    continue
            except Exception:
                log.exception("pending payment recheck failed invoice=%s",inv)
        return {"invoice_id":inv,"qr_string":oldmeta.get("qr_string"),
                "payment_url":oldmeta.get("payment_url"),"amount":int(oldmeta.get("final_amount") or amount),
                "expires_at":oldmeta.get("expires_at"),"reused":True},"ok"

    order=f"{provider.upper()}-{uuid.uuid4().hex}"
    desc=f"{typ}:{qty}"
    if metadata.get("code"):desc=f"file:{metadata['code']}"
    try:
        if provider=="bayargg":
            r=await BayarGG.create_payment(amount,desc,BAYARGG_WEBHOOK_URL,name)
        else:
            r=await Cashi.create_payment(amount,desc,name)
    except Exception:
        log.exception("provider create failed")
        r=None
    if not r:return None,"provider_error"

    metadata.update({
        "qr_string":r.get("qr_string") or r.get("qr_image"),
        "payment_url":r.get("payment_url"),
        "final_amount":r.get("final_amount") or r.get("amount") or amount,
        "expires_at":_parse_dt(r.get("expires_at")),
    })
    await p.execute("""
        INSERT INTO purchases(
            user_id,purchase_type,quantity,amount,provider,order_id,invoice_id,metadata,expires_at
        )
        VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)
        ON CONFLICT(invoice_id) DO NOTHING
    """,uid,typ,qty,amount,provider,order,r["invoice_id"],json.dumps(metadata),_parse_dt(r.get("expires_at")))
    return r,"ok"

async def _transaction_post(bot,typ,uid,qty,amount,provider,meta=None):
    try:
        from config import TRANSACTION_CHAT_ID,TRANSACTION_CHANNEL_URL
        if not TRANSACTION_CHAT_ID:return
        label={"points":"🪙 Buy Poin","stars":"⭐ Buy Star","vip":"💎 Buy VIP","creator":"👑 Buy Creator","deposit":"💰 Deposit","file":"📂 Buy Code"}.get(typ,typ)
        await bot.send_message(TRANSACTION_CHAT_ID,
            f"💳 <b>TRANSACTION SUCCESS</b>\n\n"
            f"👤 User ID: <code>{uid}</code>\n"
            f"📦 Type: <b>{label}</b>\n"
            f"🔢 Quantity: <b>{qty:g}</b>\n"
            f"💰 Amount: <b>Rp{int(amount):,}</b>\n"
            f"🏦 Provider: <b>{provider.upper()}</b>\n"
            f"🔗 Channel: {TRANSACTION_CHANNEL_URL}".replace(",","."),parse_mode="HTML")
    except Exception:log.exception("transaction notify failed")

async def finalize_purchase(invoice,status_amount=None):
    p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            row=await c.fetchrow("SELECT * FROM purchases WHERE invoice_id=$1 FOR UPDATE",str(invoice))
            if not row:return False
            if row["status"]=="paid":return True
            if row["status"]!="pending":return False

            expected=int(row["amount"] or 0)
            meta=row["metadata"] or {}
            accepted={expected}
            try:
                if meta.get("final_amount") is not None:accepted.add(int(float(meta["final_amount"])))
            except Exception:pass
            if status_amount is not None:
                try:
                    actual=int(float(status_amount))
                except (TypeError,ValueError):
                    return False
                # Gateway fees may make the settled amount higher, but never
                # accept an amount below the local order amount.
                if actual < expected:
                    log.error("PAYMENT AMOUNT MISMATCH invoice=%s expected=%s actual=%s accepted=%s",invoice,expected,actual,accepted)
                    return False

            typ=row["purchase_type"]; uid=int(row["user_id"]); qty=row["quantity"]
            # Validate file before changing status so a bad code cannot create
            # a paid-but-undelivered transaction.
            file_row=None
            if typ=="file":
                code=str(meta.get("code") or "").strip()
                file_row=await c.fetchrow("SELECT owner_id,price_idr FROM files WHERE code=$1 AND active=TRUE FOR UPDATE",code)
                if not file_row:return False
                price=int(file_row["price_idr"] or expected)
                if price!=expected:return False

            await c.execute("UPDATE purchases SET status='paid',paid_at=NOW() WHERE id=$1 AND status='pending'",row["id"])

            if typ=="points":
                await c.execute("UPDATE users SET points=points+$1 WHERE user_id=$2",qty,uid)
            elif typ=="stars":
                await c.execute("UPDATE users SET stars=stars+$1 WHERE user_id=$2",qty,uid)
            elif typ=="vip":
                days=int(qty)
                await c.execute("""
                    UPDATE users SET vip=TRUE,
                    vip_until=GREATEST(COALESCE(vip_until,NOW()),NOW())+($1||' days')::interval,
                    vip_plan_days=$1,
                    vip_daily_limit=CASE
                        WHEN $1=1 THEN 2 WHEN $1=3 THEN 4 WHEN $1=5 THEN 6
                        WHEN $1=7 THEN 7 WHEN $1=10 THEN 10 WHEN $1=15 THEN 15
                        WHEN $1=30 THEN 30 ELSE GREATEST($1,2) END
                    WHERE user_id=$2
                """,days,uid)
            elif typ=="creator":
                await c.execute("UPDATE users SET creator_status=CASE WHEN creator_status='approved' THEN creator_status ELSE 'pending' END WHERE user_id=$1",uid)
            elif typ=="deposit":
                await c.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2",expected,uid)
            elif typ=="file":
                code=str(meta.get("code") or "")
                creator_id=int(file_row["owner_id"])
                price=int(file_row["price_idr"] or expected)
                income=(price*70)//100
                await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)
                await c.execute("UPDATE users SET total_unlocks=total_unlocks+1 WHERE user_id=$1",uid)
                if creator_id!=uid and income>0:
                    await c.execute("UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1,points=points+1 WHERE user_id=$2",income,creator_id)
                await c.execute("""
                    INSERT INTO unlock_transactions(
                        user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at
                    ) VALUES($1,$2,$3,'qr',$4,1,$5,NOW()+INTERVAL '24 hours')
                """,uid,creator_id,code,price,income)

    try:
        from bot import bot
        await _transaction_post(bot,typ,uid,float(qty),int(row["amount"]),str(row["provider"]),meta)
        if typ=="file":
            await bot.send_message(uid,f'✅ <b>Payment successful</b>\n\n🔑 Code: <code>{meta.get("code")}</code>\n📥 Pembayaran berhasil dan akses code sudah aktif.',parse_mode="HTML")
        elif typ=="deposit":
            bal=await p.fetchval("SELECT balance FROM users WHERE user_id=$1",uid)
            await bot.send_message(uid,f'✅ Deposit berhasil.\n💰 Saldo sekarang: <b>Rp{int(bal or 0):,}</b>'.replace(",","."),parse_mode="HTML")
        elif typ=="vip":
            await bot.send_message(uid,f'💎 <b>VIP berhasil diaktifkan!</b>\nDurasi: <b>{int(qty)} hari</b>.',parse_mode="HTML")
        elif typ=="creator":
            await bot.send_message(uid,'✅ Pembayaran Creator berhasil.\n👑 Pendaftaran Creator tercatat dan menunggu verifikasi admin.',parse_mode="HTML")
        else:
            await bot.send_message(uid,'✅ Pembayaran berhasil. Saldo/paket sudah masuk otomatis.')
    except Exception:
        log.exception("post-payment notification failed")
    return True
