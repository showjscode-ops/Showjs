from __future__ import annotations

import re
from datetime import datetime,timedelta,timezone
import html,json,os,tempfile,asyncio,re
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,InputMediaPhoto,InputMediaVideo,InputMediaDocument,InputMediaAudio,BufferedInputFile
from database import get_pool
from utils.economy import unlock,is_creator,is_vip,vip_allowed
from utils.media_sender import deliver_one
from utils.notify_channel import notify
from utils.callback_loading import loading
from config import STAR_PER_MEDIA,MEDIA_SEND_DELAY_MS,BOT_USERNAME
from utils.payments import create_purchase,qr_bytes,enabled
from handlers.payments import ManualProofState
router=Router()

# ---------------------------------------------------------------------------
# 3-LANGUAGE USER TEXT
# Language is read from the same user preference used by the Dashboard.
# ---------------------------------------------------------------------------
try:
    from utils.i18n import get_lang
except Exception:
    async def get_lang(uid):
        return "id"

def _L(lang, key, **kw):
    lang = str(lang or "id").lower()
    if lang not in ("id", "en", "zh"):
        lang = "id"
    T = {
        "insufficient_points": {"id":"❌ <b>Poin tidak cukup</b>\n\n🪙 Dibutuhkan: <b>{need} Poin</b>\n🪙 Poin kamu: <b>{balance}</b>\n\nSilakan beli Poin terlebih dahulu.","en":"❌ <b>Not enough Points</b>\n\n🪙 Required: <b>{need} Points</b>\n🪙 Your Points: <b>{balance}</b>\n\nPlease buy Points first.","zh":"❌ <b>积分不足</b>\n\n🪙 需要：<b>{need} 积分</b>\n🪙 你的积分：<b>{balance}</b>\n\n请先购买积分。"},
        "insufficient_star": {"id":"❌ <b>Star tidak cukup</b>\n\n⭐ Dibutuhkan: <b>{need} Star</b>\n⭐ Star kamu: <b>{balance} Star</b>\n\nSilakan beli Star terlebih dahulu.","en":"❌ <b>Not enough Stars</b>\n\n⭐ Required: <b>{need} Stars</b>\n⭐ Your Stars: <b>{balance} Stars</b>\n\nPlease buy Stars first.","zh":"❌ <b>Star 不足</b>\n\n⭐ 需要：<b>{need} Star</b>\n⭐ 你的 Star：<b>{balance} Star</b>\n\n请先购买 Star。"},
        "insufficient_balance": {"id":"❌ <b>Saldo tidak cukup</b>\n\n💰 Dibutuhkan: <b>{need}</b>\n💰 Saldo kamu: <b>{balance}</b>\n\nSilakan isi saldo terlebih dahulu.","en":"❌ <b>Insufficient Balance</b>\n\n💰 Required: <b>{need}</b>\n💰 Your balance: <b>{balance}</b>\n\nPlease deposit funds first.","zh":"❌ <b>余额不足</b>\n\n💰 需要：<b>{need}</b>\n💰 你的余额：<b>{balance}</b>\n\n请先充值。"},
        "buy_points":{"id":"🛒 Buy Poin","en":"🛒 Buy Points","zh":"🛒 购买积分"},
        "buy_star":{"id":"🛒 Buy Star","en":"🛒 Buy Stars","zh":"🛒 购买 Star"},
        "deposit":{"id":"💳 Deposit","en":"💳 Deposit","zh":"💳 充值"},
        "back":{"id":"🔙 Kembali","en":"🔙 Back","zh":"🔙 返回"},
        "invalid_code":{"id":"❌ Code tidak valid.","en":"❌ Invalid code.","zh":"❌ Code 无效。"},
        "send_code":{"id":"📥 Kirim CODE yang ingin dibuka.","en":"📥 Send the CODE you want to open.","zh":"📥 发送你要打开的 CODE。"},
        "not_found":{"id":"❌ Code tidak ditemukan.","en":"❌ Code not found.","zh":"❌ 未找到该 Code。"},
        "like":"Like", "hate":"Hate", "favorite":{"id":"⭐ Favorit","en":"⭐ Favorite","zh":"⭐ 收藏"},
        "open_code":{"id":"📥 Buka Code","en":"📥 Open Code","zh":"📥 打开 Code"},
        "own_open":{"id":"📂 Buka Code (Gratis)","en":"📂 Open Code (Free)","zh":"📂 打开 Code（免费）"},
        "own_title":{"id":"🔓 <b>CODE MILIK SENDIRI</b>","en":"🔓 <b>YOUR OWN CODE</b>","zh":"🔓 <b>你的 Code</b>"},
        "own_desc":{"id":"Media milikmu dapat dibuka tanpa Poin, Star, atau Saldo.","en":"Your media can be opened without Points, Stars, or Balance.","zh":"你的媒体无需积分、Star 或余额即可打开。"},
        "paid_access":{"id":"<b>CODE SUDAH DIBAYAR</b>\n\nCode: <code>{code}</code>\nNominal: {price}\n\nAkses aktif sampai 24 jam setelah pembayaran.","en":"<b>CODE ALREADY PAID</b>\n\nCode: <code>{code}</code>\nAmount: {price}\n\nAccess is active for 24 hours after payment.","zh":"<b>CODE 已付款</b>\n\nCode：<code>{code}</code>\n金额：{price}\n\n付款后访问权限有效 24 小时。"},
        "open_paid":{"id":"Buka Media","en":"Open Media","zh":"打开媒体"},
        "vip_open":{"id":"💎 Buka Gratis (VIP)","en":"💎 Open Free (VIP)","zh":"💎 免费打开（VIP）"},
        "open_title":{"id":"🔐 <b>OPEN CODE</b>","en":"🔐 <b>OPEN CODE</b>","zh":"🔐 <b>打开 CODE</b>"},
        "choose_payment":{"id":"Pilih pembayaran:","en":"Choose a payment method:","zh":"请选择支付方式："},
        "choose_open":{"id":"Pilih cara membuka:","en":"Choose how to open:","zh":"请选择打开方式："},
        "not_enough":{"id":"❌ Saldo tidak cukup","en":"❌ Insufficient balance","zh":"❌ 余额不足"},
        "cannot_open":{"id":"❌ Tidak dapat membuka media.","en":"❌ Unable to open the media.","zh":"❌ 无法打开媒体。"},
        "success_open":{"id":"✅ Berhasil dibuka!","en":"✅ Opened successfully!","zh":"✅ 打开成功！"},
        "own_success":{"id":"✅ Membuka code milik sendiri...","en":"✅ Opening your own code...","zh":"✅ 正在打开你的 Code…"},
        "private_chat":{"id":"Buka chat pribadi dengan bot untuk menerima media.","en":"Open a private chat with the bot to receive the media.","zh":"请打开与机器人的私聊以接收媒体。"},
        "media_corrupt":{"id":"❌ Data media rusak: {err}","en":"❌ Media data is corrupted: {err}","zh":"❌ 媒体数据损坏：{err}"},
        "all_sent":{"id":"Semua media sudah terkirim.","en":"All media have already been sent.","zh":"所有媒体都已发送。"},
        "sent":{"id":"📦 <b>{sent}</b> media berhasil dikirim.","en":"📦 <b>{sent}</b> media sent successfully.","zh":"📦 已成功发送 <b>{sent}</b> 个媒体。"},
        "done":{"id":"✅ <b>Semua media selesai dikirim.</b>\n📦 Total: <b>{total}</b>","en":"✅ <b>All media have been sent.</b>\n📦 Total: <b>{total}</b>","zh":"✅ <b>所有媒体发送完成。</b>\n📦 总数：<b>{total}</b>"},
        "continue":{"id":"▶️ Lanjut kirim","en":"▶️ Continue","zh":"▶️ 继续发送"},
        "cancel":{"id":"❌ Batal","en":"❌ Cancel","zh":"❌ 取消"},
        "stopped":{"id":"Pengiriman dihentikan.","en":"Sending stopped.","zh":"发送已停止。"},
        "cancelled":{"id":"❌ Pengiriman media dibatalkan.","en":"❌ Media delivery cancelled.","zh":"❌ 媒体发送已取消。"},
        "expired":{"id":"⏳ Akses code sudah habis.","en":"⏳ Code access has expired.","zh":"⏳ Code 访问权限已过期。"},
        "not_owner":{"id":"❌ Code ini bukan milikmu.","en":"❌ This code does not belong to you.","zh":"❌ 此 Code 不属于你。"},
        "payment_success":{"id":"✅ Pembayaran berhasil!","en":"✅ Payment successful!","zh":"✅ 支付成功！"},
        "payment_fail":{"id":"❌ Pembayaran dengan Saldo gagal.","en":"❌ Balance payment failed.","zh":"❌ 余额支付失败。"},
        "free_code":{"id":"Code ini gratis.","en":"This code is free.","zh":"此 Code 免费。"},
        "qr_min":{"id":"Tidak ada metode QR yang mendukung nominal ini.","en":"No QR payment method supports this amount.","zh":"没有支持此金额的二维码支付方式。"},
        "qr_missing":{"id":"QR manual belum dipasang admin.","en":"Manual QR has not been configured by the admin.","zh":"管理员尚未设置手动二维码。"},
        "all_payment_fail":{"id":"Semua metode pembayaran tidak tersedia.","en":"All payment methods are unavailable.","zh":"所有支付方式均不可用。"},
        "all_payment_amount":{"id":"Semua metode pembayaran tidak tersedia untuk nominal ini.","en":"No payment method is available for this amount.","zh":"此金额没有可用的支付方式。"},
        "check_payment":{"id":"Cek Pembayaran","en":"Check Payment","zh":"检查支付"},
        "cancel_payment":{"id":"Batal","en":"Cancel","zh":"取消"},
        "manual_caption":{"id":"QR MANUAL\n\nCode: <code>{code}</code>\nNominal: {amount}\n\nSetelah membayar, tekan Cek Pembayaran lalu kirim screenshot bukti.","en":"MANUAL QR\n\nCode: <code>{code}</code>\nAmount: {amount}\n\nAfter paying, tap Check Payment and send the payment screenshot.","zh":"手动二维码\n\nCode：<code>{code}</code>\n金额：{amount}\n\n付款后点击“检查支付”，然后发送付款截图。"},
        "payment_caption":{"id":"PAYMENT\n\nCode: <code>{code}</code>\nNominal: {amount}\nProvider: {provider}\nInvoice: <code>{invoice}</code>\n\nSetelah membayar, tekan Cek Pembayaran.","en":"PAYMENT\n\nCode: <code>{code}</code>\nAmount: {amount}\nProvider: {provider}\nInvoice: <code>{invoice}</code>\n\nAfter paying, tap Check Payment.","zh":"支付\n\nCode：<code>{code}</code>\n金额：{amount}\n支付商：{provider}\nInvoice：<code>{invoice}</code>\n\n付款后点击“检查支付”。"},
        "media_missing":{"id":"⚠️ <b>MEDIA TIDAK TERSEDIA</b>","en":"⚠️ <b>MEDIA UNAVAILABLE</b>","zh":"⚠️ <b>媒体不可用</b>"},
        "failed_sent":{"id":"Media gagal dikirim: <b>{n}</b>","en":"Failed to send media: <b>{n}</b>","zh":"发送失败的媒体：<b>{n}</b>"},
    }
    v=T.get(key)
    if isinstance(v,str): return v.format(**kw)
    if isinstance(v,dict): return v.get(lang,v["id"]).format(**kw)
    return key.format(**kw)

async def _lang(uid):
    try:
        v=await get_lang(uid)
        if isinstance(v,str): return v
    except Exception:
        pass
    return "id"

def _btn(lang, key):
    return _L(lang,key)

async def _insufficient_notice(c, method, cost):
    """Show a clear insufficient-balance notice with the correct purchase action."""
    method = str(method or "").lower()
    uid = c.from_user.id
    lang = await _lang(uid)
    pool = await get_pool()
    if method == "points":
        current = await pool.fetchval("SELECT COALESCE(points,0) FROM users WHERE user_id=$1", uid)
        current = float(current or 0)
        need = float(cost or 0)
        label = f"{need:g}"
        balance = f"{current:g}"
        text = (
            _L(lang,'insufficient_points',need=label,balance=balance)
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_L(lang,'buy_points'), callback_data="buy_points")],
            [InlineKeyboardButton(text="🔙 Kembali", callback_data="home")]
        ])
    elif method == "star":
        current = await pool.fetchval("SELECT COALESCE(stars,0) FROM users WHERE user_id=$1", uid)
        current = float(current or 0)
        need = float(cost or 0)
        text = (
            _L(lang,'insufficient_star',need=f'{need:g}',balance=f'{current:g}')
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_L(lang,'buy_star'), callback_data="buy_stars")],
            [InlineKeyboardButton(text="🔙 Kembali", callback_data="home")]
        ])
    else:
        current = await pool.fetchval("SELECT COALESCE(balance,0) FROM users WHERE user_id=$1", uid)
        current = int(current or 0)
        need = int(cost or 0)
        text = (
            _L(lang,'insufficient_balance',need=fmt(need),balance=fmt(current))
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_L(lang,'deposit'), callback_data="deposit")],
            [InlineKeyboardButton(text="🔙 Kembali", callback_data="home")]
        ])
    try:
        await c.answer(_L(lang,'not_enough').replace('<b>','').replace('</b>',''), show_alert=True)
    except Exception:
        pass
    return await c.message.answer(text, parse_mode="HTML", reply_markup=kb)

def fmt(n): return f"Rp{int(n):,}".replace(',','.')

async def code_info_kb(code,title='Code',lang='id'):
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text=f'📝 {title[:40]}',callback_data=f'getcode:{code}')],
      [InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{code}'),InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{code}'),InlineKeyboardButton(text=_L(lang,'favorite'),callback_data=f'react:favorite:{code}')],
      [InlineKeyboardButton(text=_L(lang,'open_code'),callback_data=f'getcode:{code}')],
      [InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]
    ])

async def get_file(code):
    return await (await get_pool()).fetchrow("SELECT * FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)

async def has_permanent_or_paid_unlock(uid,code):
    p=await get_pool()
    return bool(await p.fetchval("""SELECT 1 FROM unlock_transactions WHERE user_id=$1 AND code=$2
        AND payment_type IN ('balance','qr','admin') AND expires_at>NOW() ORDER BY id DESC LIMIT 1""",uid,code))

async def has_permanent_access(uid,code):
    p=await get_pool()
    return bool(await p.fetchval("""SELECT 1 FROM unlock_transactions WHERE user_id=$1 AND code=$2
        AND payment_type IN ('balance','admin') AND expires_at>NOW() ORDER BY id DESC LIMIT 1""",uid,code))

async def show(m,code):
    f=await get_file(code)
    if not f:return await m.answer(_L(await _lang(m.from_user.id),'invalid_code'))
    p=await get_pool()
    await p.execute("UPDATE files SET views=views+1 WHERE code=$1", code)
    stats=await p.fetchrow("""SELECT views,likes,hates,favorites FROM files WHERE id=$1""",f['id'])
    price=int(f['price_idr'] or 0)
    paid=f"💰 Harga: <b>{fmt(price)}</b>" if price else "🆓 FREE CODE"
    await m.answer(
      f"📦 <b>{html.escape(f['title'] or 'Untitled')}</b>\n\n"
      f"🔑 <code>{html.escape(code)}</code>\n{paid}\n"
      f"👁 Views: <b>{stats['views']}</b>  👍 <b>{stats['likes']}</b>  👎 <b>{stats['hates']}</b>  ⭐ <b>{stats['favorites']}</b>\n\n"
      f"Bagikan code ini ke teman-teman untuk membuka media ini.",
      parse_mode='HTML',reply_markup=await code_info_kb(code,f['title'] or 'Code',await _lang(m.from_user.id)))

@router.callback_query(F.data=='getfile')
async def start(c):
    lang = await _lang(c.from_user.id)
    await loading(c)
    try:
        await c.message.edit_text(
            _L(await _lang(c.from_user.id),'send_code'),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_L(lang,'back'), callback_data='home')]
            ])
        )
    except Exception:
        await c.message.answer(
            _L(await _lang(c.from_user.id),'send_code'),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_L(lang,'back'), callback_data='home')]
            ])
        )

# Direct CODE input.
# Do not hard-code the random part of the code: deployments may use a
# different allowed alphabet/length.  Accept the canonical suffix
# ``<p>p<v>v<d>d`` and ignore accidental spaces/backticks around the code.
_CODE_RE = re.compile(r'^[^\s_]+_[^\s_]+_\d+p\d+v\d+d$', re.I)

@router.message(F.chat.type == 'private', F.text.regexp(re.compile(r'^`?[^\s_]+_[^\s_]+_\d+p\d+v\d+d`?$', re.IGNORECASE)))
async def receive(m):
    raw=(m.text or '').strip()
    # Users often paste a code wrapped in backticks or with whitespace.
    code=raw.strip('`').strip()
    if not _CODE_RE.fullmatch(code):
        return
    await show(m,code)

@router.callback_query(F.data.startswith('getcode:'))
async def getcode(c):
    await loading(c); code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    await c.answer()
    await (await get_pool()).execute("UPDATE files SET views=views+1 WHERE code=$1", code)
    await open_choices(c,code,f)

async def open_choices(c,code,f):
    lang=await _lang(c.from_user.id)
    uid=c.from_user.id; n=int(f['media_count']); price=int(f['price_idr'] or 0)
    if int(f['owner_id']) == int(uid):
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_L(lang,'own_open'),callback_data=f'openown:{code}')],
            [InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]
        ])
        return await c.message.edit_text(
            f"{_L(lang,'own_title')}\n\n"
            f"📝 {html.escape(f['title'] or 'Untitled')}\n"
            f"🔑 <code>{html.escape(code)}</code>\n📦 {n} media\n\n"
            f"{_L(lang,'own_desc')}",
            parse_mode='HTML',reply_markup=kb
        )
    if price>0 and await has_permanent_or_paid_unlock(uid,code):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_L(lang,'open_paid'),callback_data=f'openpaid:{code}')],[InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]])
        return await c.message.edit_text(_L(lang,'paid_access',code=html.escape(code),price=fmt(price)),parse_mode='HTML',reply_markup=kb)
    if await is_vip(uid):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_L(lang,'vip_open'),callback_data=f'openvip:{code}')],[InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]])
    else:
        creator=await is_creator(uid)
        pc=n*0.5 if creator else n
        sc=n*STAR_PER_MEDIA*(0.5 if creator else 1)
        rows=[]
        rows.extend([
          [InlineKeyboardButton(
              text=f'🪙 Buka dengan {pc:g} Poin' + (' (50%)' if creator else ''),
              callback_data=f'unlockp:{code}'
          )],
          [InlineKeyboardButton(
              text=f'⭐ Buka dengan {sc:g} Star' + (' (50%)' if creator else ''),
              callback_data=f'unlocks:{code}'
          )],
        ])
        if price>0 and await enabled('payment_balance'):
            rows.append([InlineKeyboardButton(text=f'💰 Buka dengan Saldo • {fmt(price)}',callback_data=f'openbal:{code}')])
        if price>0:
            if await enabled('bayargg'): rows.append([InlineKeyboardButton(text='QR 2',callback_data=f'payfile:bayargg:{code}')])
            if await enabled('cashi'): rows.append([InlineKeyboardButton(text='QR 1',callback_data=f'payfile:cashi:{code}')])
            if await enabled('manual'): rows.append([InlineKeyboardButton(text='🧾 QR Manual',callback_data=f'payfile:manual:{code}')])
        rows.append([InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')])
        kb=InlineKeyboardMarkup(inline_keyboard=rows)
    await c.message.edit_text(
      f"🔐 <b>OPEN CODE</b>\n\n📝 {html.escape(f['title'] or 'Untitled')}\n🔑 <code>{html.escape(code)}</code>\n📦 {n} media\n"
      +(f"💰 {fmt(price)}\n\n{_L(lang,'choose_payment')}" if price else f"\n{_L(lang,'choose_open')}"),
      parse_mode='HTML',reply_markup=kb)

async def _send_b2(bot, chat_id, item, caption=None):
    # Keep one canonical media-delivery implementation.
    return await deliver_one(bot, chat_id, item, caption=caption)

async def _send_telegram_fallback(bot, chat_id, item, caption=None):
    from utils.media_sender import deliver_telegram_file_id
    return await deliver_telegram_file_id(bot, chat_id, item, caption=caption)

async def send_page(bot, chat_id, code, media, page, access_expires_at=None, permanent=False):
    start = page * 10
    chunk = media[start:start + 10]
    missing = []
    sent = 0
    total = len(media)

    for i, item in enumerate(chunk, start + 1):
        caption = (
            f"🔑 {html.escape(str(code))}\n"
            f"📁 Media ke {i}/{total}\n"
            f"🤖 @{html.escape(BOT_USERNAME)}"
        )
        delivered = False
        telegram_error = None
        b2_error = None
        last_msg = None

        # Telegram file_id is the original, already-uploaded Telegram object.
        # Prefer it first so Star/Points unlocks do not depend on B2 being alive.
        try:
            last_msg = await _send_telegram_fallback(bot, chat_id, item, caption=caption)
            delivered = True
        except Exception as exc:
            telegram_error = str(exc)

        # B2 is the secondary source. This also supports old records that may
        # not contain a Telegram file_id.
        if not delivered:
            try:
                if item.get('drive_account') is not None and item.get('drive_file_id'):
                    last_msg = await _send_b2(bot, chat_id, item, caption=caption)
                    delivered = True
                else:
                    raise RuntimeError('Backblaze metadata tidak tersedia')
            except Exception as exc:
                b2_error = str(exc)
                reason = (
                    f"Telegram file_id gagal: {str(telegram_error or 'tidak tersedia')[:180]} | "
                    f"Backblaze gagal: {str(b2_error)[:180]}"
                )
                missing.append({'index': i, 'reason': reason})

        if delivered:
            sent += 1
            try:
                mid=int(getattr(last_msg,'message_id',0) or 0)
                if mid:
                    if permanent:
                        await (await get_pool()).execute("""
                            INSERT INTO delivery_messages(user_id,chat_id,message_id,code,expires_at)
                            VALUES($1,$2,$3,$4,NOW()+INTERVAL '100 years')
                            ON CONFLICT(chat_id,message_id) DO NOTHING
                        """,chat_id,chat_id,mid,code)
                    else:
                        exp = access_expires_at
                        if exp is None:
                            exp = await (await get_pool()).fetchval("""
                                SELECT expires_at FROM unlock_transactions
                                WHERE user_id=$1 AND code=$2 AND expires_at>NOW()
                                ORDER BY expires_at DESC LIMIT 1
                            """,chat_id,code)
                        if exp is not None:
                            await (await get_pool()).execute("""
                                INSERT INTO delivery_messages(user_id,chat_id,message_id,code,expires_at)
                                VALUES($1,$2,$3,$4,$5)
                                ON CONFLICT(chat_id,message_id) DO NOTHING
                            """,chat_id,chat_id,mid,code,exp)
            except Exception:
                pass

        await asyncio.sleep(max(0, MEDIA_SEND_DELAY_MS) / 1000)

    if missing:
        lines = [
            "⚠️ <b>MEDIA TIDAK TERSEDIA</b>",
            "",
            f"🔑 <code>{html.escape(code)}</code>",
            f"Media gagal dikirim: <b>{len(missing)}</b>",
        ]
        for item in missing:
            lines.append(f"📁 Media {item.get('index', '?')}: {html.escape(str(item.get('reason', 'Sumber media tidak tersedia'))[:300])}")
        try:
            await bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
        except Exception:
            pass
    return sent, missing

async def delivery_kb(code, page, total, done=False, lang='id'):
    if done:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{code}'),
            InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{code}'),
            InlineKeyboardButton(text=_L(lang,'favorite'),callback_data=f'react:favorite:{code}')
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=_L(lang,'continue'),callback_data=f'continue:{code}:{page+1}'),
        InlineKeyboardButton(text=_L(lang,'cancel'),callback_data=f'cancelget:{code}')
    ]])

async def _access_expiry(uid, code):
    return await (await get_pool()).fetchval("""
        SELECT expires_at FROM unlock_transactions
        WHERE user_id=$1 AND code=$2 AND expires_at>NOW()
        ORDER BY expires_at DESC LIMIT 1
    """,uid,code)

async def deliver_page(c,code,page,permanent=False,access_expires_at=None):
    if c.message.chat.type != "private":
        await c.answer("Buka chat pribadi dengan bot untuk menerima media.", show_alert=True)
        return False
    f=await get_file(code)
    if not f:
        await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
        return False
    try:
        raw_media = f['media']
        media = raw_media if isinstance(raw_media, list) else json.loads(raw_media or '[]')
        if not isinstance(media, list):
            raise ValueError('media bukan array')
        media = [x for x in media if isinstance(x, dict)]
    except Exception as exc:
        await c.answer(_L(await _lang(c.from_user.id),'media_corrupt',err=str(exc)[:120]), show_alert=True)
        return False
    total=len(media)
    if page*10 >= total:
        await c.answer(_L(await _lang(c.from_user.id),'all_sent'),show_alert=True)
        return True
    sent,_=await send_page(
        c.bot,c.from_user.id,code,media,page,
        access_expires_at=access_expires_at,permanent=permanent
    )
    done=(page+1)*10 >= total
    text=(_L(await _lang(c.from_user.id),'sent',sent=sent)
          if not done else
          _L(await _lang(c.from_user.id),'done',total=total))
    await c.message.answer(text,parse_mode='HTML',
                           reply_markup=await delivery_kb(code,page,total,done=done,lang=await _lang(c.from_user.id)))
    return True

@router.callback_query(F.data.startswith('continue:'))
async def continue_delivery(c):
    lang = await _lang(c.from_user.id)
    await loading(c)
    _,code,pg=c.data.split(':',2)
    f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    permanent=int(f['owner_id'])==int(c.from_user.id)
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if not permanent and exp is None:
        return await c.answer(_L(lang,'expired'),show_alert=True)
    await c.answer()
    await deliver_page(c,code,int(pg),permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('cancelget:'))
async def cancel_delivery(c):
    await c.answer(_L(await _lang(c.from_user.id),'stopped'))
    try: await c.message.edit_text(_L(await _lang(c.from_user.id),'cancelled'))
    except Exception:
        try: await c.message.edit_reply_markup(reply_markup=None)
        except Exception: pass

async def open_media(c,method):
    lang = await _lang(c.from_user.id)
    code=c.data.split(':',1)[1]
    f=await get_file(code)
    if not f:return await c.answer('Code tidak ditemukan.',show_alert=True)
    ok,new,reason,cost=await unlock(c.from_user.id,code,int(f['media_count']),method)
    if not ok:
        if reason=='insufficient':
            return await _insufficient_notice(c,method,cost)
        if reason=='vip_quota':
            p=await get_pool()
            days=int(await p.fetchval("SELECT vip_plan_days FROM users WHERE user_id=$1",c.from_user.id) or 1)
            package=await p.fetchrow("SELECT code,name FROM vip_packages WHERE duration_days=$1 AND active ORDER BY price LIMIT 1",days)
            label=package['name'] if package else f'VIP {days} Hari'
            cb=f"vip:{package['code']}" if package else "buy_vip"
            return await c.message.answer(
                f"⚠️ <b>Kuota buka CODE VIP hari ini sudah habis.</b>\n\n💎 Paket kamu: <b>{html.escape(label)}</b>\nSilakan perpanjang VIP untuk membuka code lagi.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f'💎 Perpanjang {label}',callback_data=cb)],
                    [InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]
                ])
            )
        return await c.message.answer(_L(lang,'cannot_open'))
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    permanent=(reason=='own')
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if reason=='vip' and exp is None:
        exp=datetime.now(timezone.utc)+timedelta(days=3)
    await deliver_page(c,code,0,permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('openvip:'))
async def openvip(c):
    # A CallbackQuery must be acknowledged quickly. DB/payment/unlock work can
    # take several seconds, so acknowledge it before any awaited work.
    try:
        await c.answer()
    except Exception:
        pass
    lang = await _lang(c.from_user.id)
    code=c.data.split(':',1)[1]
    f=await get_file(code)
    if not f:
        return await c.message.answer(_L(await _lang(c.from_user.id),'not_found'))
    ok,_,reason,_=await unlock(c.from_user.id,code,int(f['media_count']),'balance')
    if not ok:
        if reason=='vip_quota':
            p=await get_pool()
            days=int(await p.fetchval("SELECT vip_plan_days FROM users WHERE user_id=$1",c.from_user.id) or 1)
            package=await p.fetchrow("SELECT code,name FROM vip_packages WHERE duration_days=$1 AND active ORDER BY price LIMIT 1",days)
            label=package['name'] if package else f'VIP {days} Hari'
            cb=f"vip:{package['code']}" if package else "buy_vip"
            return await c.message.answer(
                f"⚠️ <b>Kuota buka CODE VIP hari ini sudah habis.</b>\n\n💎 Paket kamu: <b>{html.escape(label)}</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f'💎 Perpanjang {label}',callback_data=cb)],
                    [InlineKeyboardButton(text=_L(lang,'back'),callback_data='home')]
                ])
            )
        return await c.message.answer(_L(lang,'cannot_open'))
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    exp=await _access_expiry(c.from_user.id,code)
    await deliver_page(c,code,0,permanent=False,access_expires_at=exp)

@router.callback_query(F.data.startswith('openown:'))
async def openown(c):
    lang = await _lang(c.from_user.id)
    code=c.data.split(':',1)[1]
    f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    if int(f['owner_id']) != int(c.from_user.id):
        return await c.answer(_L(lang,'not_owner'),show_alert=True)
    await c.answer(_L(await _lang(c.from_user.id),'own_success'))
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    await deliver_page(c,code,0,permanent=True,access_expires_at=None)

@router.callback_query(F.data.startswith('unlockp:'))
async def up(c): await open_media(c,'points')
@router.callback_query(F.data.startswith('unlocks:'))
async def us(c): await open_media(c,'star')

@router.callback_query(F.data.startswith('openpaid:'))
async def openpaid(c):
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('Code tidak ditemukan.',show_alert=True)
    if not await has_permanent_or_paid_unlock(c.from_user.id,code):
        return await c.answer(_L(await _lang(c.from_user.id),'expired'),show_alert=True)
    await c.answer(_L(await _lang(c.from_user.id),'success_open'))
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    await deliver_page(c,code,0,permanent=False)

@router.callback_query(F.data.startswith('openbal:'))
async def openbal(c):
    lang = await _lang(c.from_user.id)
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    ok,_,reason,cost=await unlock(c.from_user.id,code,int(f['media_count']),'balance')
    if not ok:
        if reason=='insufficient': return await _insufficient_notice(c,'balance',cost)
        return await c.answer(_L(lang,'payment_fail'),show_alert=True)
    await c.answer('✅ Pembayaran berhasil!')
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    await deliver_page(c,code,0,permanent=False)

@router.callback_query(F.data.startswith('payfile:'))
async def payfile(c,state):
    lang = await _lang(c.from_user.id)
    _,requested,code=c.data.split(':',2); f=await get_file(code)
    if not f:return await c.answer('Code tidak ditemukan.',show_alert=True)
    amount=int(f['price_idr'] or 0)
    if amount<=0:return await c.answer(_L(lang,'free_code'),show_alert=True)
    requested=str(requested).lower()
    # QR 1 (BayarGG) has a provider minimum of Rp5.000. Automatically
    # reroute smaller amounts to Cashi, and if Cashi is unavailable/fails,
    # fall back to the configured manual QR.
    provider=requested
    if requested=='bayargg' and amount<5000:
        if await enabled('cashi'):
            provider='cashi'
        elif await enabled('manual'):
            provider='manual'
        else:
            return await c.answer('Tidak ada metode QR yang mendukung nominal ini.',show_alert=True)
    if provider=='manual':
        qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
        if not qr:return await c.answer('QR manual belum dipasang admin.',show_alert=True)
        p=await get_pool()
        row=await p.fetchrow("""INSERT INTO manual_deposits(user_id,amount,target_code,target_type,quantity,status)
          VALUES($1,$2,$3,'file',1,'pending') RETURNING id""",c.from_user.id,amount,code)
        msg=await c.message.answer_photo(qr,caption=f"QR MANUAL\n\nCode: <code>{html.escape(code)}</code>\nNominal: {fmt(amount)}\n\nSetelah membayar, tekan Cek Pembayaran lalu kirim screenshot bukti.",parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Cek Pembayaran',callback_data=f'mancheck:{row["id"]}')],[InlineKeyboardButton(text='Batal',callback_data=f'mancancel:{row["id"]}')]]))
        await p.execute("UPDATE manual_deposits SET qr_message_id=$1 WHERE id=$2",msg.message_id,row['id'])
        return
    r,status=await create_purchase(c.from_user.id,'file',1,amount,provider,c.from_user.full_name,{"code":code})
    # If the selected provider cannot accept the amount or is temporarily unavailable,
    # continue automatically to Cashi, then Manual QR.
    if not r and provider=='bayargg' and await enabled('cashi'):
        provider='cashi'; r,status=await create_purchase(c.from_user.id,'file',1,amount,provider,c.from_user.full_name,{"code":code})
    if not r and await enabled('manual'):
        provider='manual'
        qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
        if not qr:return await c.answer('Semua metode pembayaran tidak tersedia.',show_alert=True)
        p=await get_pool(); row=await p.fetchrow("INSERT INTO manual_deposits(user_id,amount,target_code,target_type,quantity,status) VALUES($1,$2,$3,'file',1,'pending') RETURNING id",c.from_user.id,amount,code)
        msg=await c.message.answer_photo(qr,caption=f"QR MANUAL\n\nCode: <code>{html.escape(code)}</code>\nNominal: {fmt(amount)}\n\nSetelah membayar, tekan Cek Pembayaran lalu kirim screenshot bukti.",parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Cek Pembayaran',callback_data=f'mancheck:{row["id"]}')],[InlineKeyboardButton(text='Batal',callback_data=f'mancancel:{row["id"]}')]]))
        await p.execute("UPDATE manual_deposits SET qr_message_id=$1 WHERE id=$2",msg.message_id,row['id']); return
    if not r:return await c.answer('Semua metode pembayaran tidak tersedia untuk nominal ini.',show_alert=True)
    data=qr_bytes(r.get('qr_string')); text=f"PAYMENT\n\nCode: <code>{code}</code>\nNominal: {fmt(amount)}\nProvider: {provider.upper()}\nInvoice: <code>{r['invoice_id']}</code>\n\nSetelah membayar, tekan Cek Pembayaran."
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Cek Pembayaran',callback_data=f'paycheck:{r["invoice_id"]}')],[InlineKeyboardButton(text='Batal',callback_data=f'paycancel:{r["invoice_id"]}')]])
    if data: await c.message.answer_photo(BufferedInputFile(data,filename='payment.png'),caption=text,parse_mode='HTML',reply_markup=kb)
    else: await c.message.answer(text,parse_mode='HTML',reply_markup=kb)

@router.callback_query(F.data.startswith('page:'))
async def page(c):
    lang = await _lang(c.from_user.id)
    _,code,pg=c.data.split(':',2)
    await loading(c)
    f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    permanent=int(f['owner_id'])==int(c.from_user.id)
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if not permanent and exp is None:
        return await c.answer(_L(lang,'expired'),show_alert=True)
    await c.answer()
    await deliver_page(c,code,int(pg),permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('react:'))
async def react(c):
    _,reaction,code=c.data.split(':',2); p=await get_pool()
    f=await get_file(code)
    if not f:return await c.answer(_L(await _lang(c.from_user.id),'not_found'),show_alert=True)
    row=await p.fetchrow("SELECT 1 FROM code_reactions WHERE user_id=$1 AND code=$2 AND reaction=$3",c.from_user.id,code,reaction)
    col={'like':'likes','hate':'hates','favorite':'favorites'}[reaction]
    if row:
        await p.execute("DELETE FROM code_reactions WHERE user_id=$1 AND code=$2 AND reaction=$3",c.from_user.id,code,reaction)
        await p.execute(f"UPDATE files SET {col}=GREATEST({col}-1,0) WHERE code=$1",code)
    else:
        await p.execute("INSERT INTO code_reactions(user_id,code,reaction) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",c.from_user.id,code,reaction)
        await p.execute(f"UPDATE files SET {col}={col}+1 WHERE code=$1",code)
    s=await p.fetchrow("SELECT likes,hates,favorites,views FROM files WHERE code=$1",code)
    await c.answer(f"👍 {s['likes']}  👎 {s['hates']}  ⭐ {s['favorites']}")
