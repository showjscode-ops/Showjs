
from __future__ import annotations
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

def fmt(n): return f"Rp{int(n):,}".replace(',','.')

def code_info_kb(code,title='Code'):
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text=f'📝 {title[:40]}',callback_data=f'getcode:{code}')],
      [InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{code}'),InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{code}'),InlineKeyboardButton(text='⭐ Favorit',callback_data=f'react:favorite:{code}')],
      [InlineKeyboardButton(text='📥 Buka Code',callback_data=f'getcode:{code}')],
      [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
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
    if not f:return await m.answer('❌ Code tidak valid.')
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
      parse_mode='HTML',reply_markup=code_info_kb(code,f['title'] or 'Code'))

@router.callback_query(F.data=='getfile')
async def start(c): await loading(c); await c.message.answer('📥 Kirim CODE yang ingin dibuka.')

# Direct CODE input.
# Do not hard-code the random part of the code: deployments may use a
# different allowed alphabet/length.  Accept the canonical suffix
# ``<p>p<v>v<d>d`` and ignore accidental spaces/backticks around the code.
_CODE_RE = re.compile(r'^[^\s_]+_[^\s_]+_\d+p\d+v\d+d$', re.I)

@router.message(F.chat.type == 'private', F.text.regexp(r'^`?[^\s_]+_[^\s_]+_\d+p\d+v\d+d`?$', mode='i'))
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
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    await c.answer()
    await (await get_pool()).execute("UPDATE files SET views=views+1 WHERE code=$1", code)
    await open_choices(c,code,f)

async def open_choices(c,code,f):
    uid=c.from_user.id; n=int(f['media_count']); price=int(f['price_idr'] or 0)
    if int(f['owner_id']) == int(uid):
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📂 Buka Code (Gratis)',callback_data=f'openown:{code}')],
            [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
        ])
        return await c.message.edit_text(
            f"🔓 <b>CODE MILIK SENDIRI</b>\n\n"
            f"📝 {html.escape(f['title'] or 'Untitled')}\n"
            f"🔑 <code>{html.escape(code)}</code>\n📦 {n} media\n\n"
            f"Media milikmu dapat dibuka tanpa Poin, Star, atau Saldo.",
            parse_mode='HTML',reply_markup=kb
        )
    if price>0 and await has_permanent_or_paid_unlock(uid,code):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Buka Media',callback_data=f'openpaid:{code}')],[InlineKeyboardButton(text='Kembali',callback_data='home')]])
        return await c.message.edit_text(f"<b>CODE SUDAH DIBAYAR</b>\n\nCode: <code>{html.escape(code)}</code>\nNominal: {fmt(price)}\n\nAkses aktif sampai 24 jam setelah pembayaran.",parse_mode='HTML',reply_markup=kb)
    if await is_vip(uid):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💎 Buka Gratis (VIP)',callback_data=f'openvip:{code}')],[InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]])
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
        rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
        kb=InlineKeyboardMarkup(inline_keyboard=rows)
    await c.message.edit_text(
      f"🔐 <b>OPEN CODE</b>\n\n📝 {html.escape(f['title'] or 'Untitled')}\n🔑 <code>{html.escape(code)}</code>\n📦 {n} media\n"
      +(f"💰 {fmt(price)}\n\nPilih pembayaran:" if price else "\nPilih cara membuka:"),
      parse_mode='HTML',reply_markup=kb)

async def _send_b2(bot, chat_id, item, caption=None):
    from utils.b2_storage import b2_pool
    path, _ = await b2_pool.download(int(item['drive_account']), str(item['drive_file_id']))
    try:
        from aiogram.types import FSInputFile
        inp = FSInputFile(path)
        typ = str(item.get('type') or 'document').lower()
        if typ == 'photo': return await bot.send_photo(chat_id, inp, caption=caption)
        if typ == 'video': return await bot.send_video(chat_id, inp, caption=caption)
        if typ == 'audio': return await bot.send_audio(chat_id, inp, caption=caption)
        return await bot.send_document(chat_id, inp, caption=caption)
    finally:
        try: os.remove(path)
        except OSError: pass

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
        b2_error = None
        last_msg = None
        try:
            if item.get('drive_account') is not None and item.get('drive_file_id'):
                last_msg = await _send_b2(bot, chat_id, item, caption=caption)
                delivered = True
        except Exception as exc:
            b2_error = str(exc)

        if not delivered:
            try:
                last_msg = await _send_telegram_fallback(bot, chat_id, item, caption=caption)
                delivered = True
            except Exception as exc:
                reason = "Backblaze dan Telegram file_id tidak tersedia"
                if b2_error:
                    reason = f"Backblaze gagal; Telegram file_id gagal: {str(exc)[:220]}"
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

def delivery_kb(code, page, total, done=False):
    if done:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{code}'),
            InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{code}'),
            InlineKeyboardButton(text='⭐ Favorit',callback_data=f'react:favorite:{code}')
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='▶️ Lanjut kirim',callback_data=f'continue:{code}:{page+1}'),
        InlineKeyboardButton(text='❌ Batal',callback_data=f'cancelget:{code}')
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
        await c.answer('❌ Code tidak ditemukan.',show_alert=True)
        return False
    media=f['media'] if isinstance(f['media'],list) else json.loads(f['media'] or '[]')
    total=len(media)
    if page*10 >= total:
        await c.answer('Semua media sudah terkirim.',show_alert=True)
        return True
    sent,_=await send_page(
        c.bot,c.from_user.id,code,media,page,
        access_expires_at=access_expires_at,permanent=permanent
    )
    done=(page+1)*10 >= total
    text=(f"📦 <b>{sent}</b> media berhasil dikirim."
          if not done else
          f"✅ <b>Semua media selesai dikirim.</b>\n📦 Total: <b>{total}</b>")
    await c.message.answer(text,parse_mode='HTML',
                           reply_markup=delivery_kb(code,page,total,done=done))
    return True

@router.callback_query(F.data.startswith('continue:'))
async def continue_delivery(c):
    await loading(c)
    _,code,pg=c.data.split(':',2)
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    permanent=int(f['owner_id'])==int(c.from_user.id)
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if not permanent and exp is None:
        return await c.answer('⏳ Akses code sudah habis.',show_alert=True)
    await c.answer()
    await deliver_page(c,code,int(pg),permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('cancelget:'))
async def cancel_delivery(c):
    await c.answer('Pengiriman dihentikan.')
    try: await c.message.edit_text('❌ Pengiriman media dibatalkan.')
    except Exception:
        try: await c.message.edit_reply_markup(reply_markup=None)
        except Exception: pass

async def open_media(c,method):
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
                    [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
                ])
            )
        return await c.answer('❌ Tidak dapat membuka media.',show_alert=True)
    await c.answer('✅ Berhasil dibuka!')
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    permanent=(reason=='own')
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if reason=='vip' and exp is None:
        exp=datetime.now(timezone.utc)+timedelta(days=3)
    await deliver_page(c,code,0,permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('openvip:'))
async def openvip(c):
    code=c.data.split(':',1)[1]
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
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
                    [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
                ])
            )
        return await c.answer('❌ Tidak dapat membuka.',show_alert=True)
    await c.answer('✅ Berhasil dibuka!')
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    exp=await _access_expiry(c.from_user.id,code)
    await deliver_page(c,code,0,permanent=False,access_expires_at=exp)

@router.callback_query(F.data.startswith('openown:'))
async def openown(c):
    code=c.data.split(':',1)[1]
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    if int(f['owner_id']) != int(c.from_user.id):
        return await c.answer('❌ Code ini bukan milikmu.',show_alert=True)
    await c.answer('✅ Membuka code milik sendiri...')
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
        return await c.answer('Akses pembayaran sudah tidak aktif.',show_alert=True)
    await c.answer('Berhasil dibuka!')
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    await deliver_page(c,code,0,permanent=False)

@router.callback_query(F.data.startswith('openbal:'))
async def openbal(c):
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    ok,_,reason,cost=await unlock(c.from_user.id,code,int(f['media_count']),'balance')
    if not ok:
        if reason=='insufficient': return await _insufficient_notice(c,'balance',cost)
        return await c.answer('❌ Pembayaran dengan Saldo gagal.',show_alert=True)
    await c.answer('✅ Pembayaran berhasil!')
    from utils.group_notify import notify_code_opened
    await notify_code_opened(c.bot, code, c.from_user.id, c.from_user.username, c.from_user.full_name)
    await deliver_page(c,code,0,permanent=False)

@router.callback_query(F.data.startswith('payfile:'))
async def payfile(c,state):
    _,requested,code=c.data.split(':',2); f=await get_file(code)
    if not f:return await c.answer('Code tidak ditemukan.',show_alert=True)
    amount=int(f['price_idr'] or 0)
    if amount<=0:return await c.answer('Code ini gratis.',show_alert=True)
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
    _,code,pg=c.data.split(':',2)
    await loading(c)
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    permanent=int(f['owner_id'])==int(c.from_user.id)
    exp=None if permanent else await _access_expiry(c.from_user.id,code)
    if not permanent and exp is None:
        return await c.answer('⏳ Akses code sudah habis.',show_alert=True)
    await c.answer()
    await deliver_page(c,code,int(pg),permanent=permanent,access_expires_at=exp)

@router.callback_query(F.data.startswith('react:'))
async def react(c):
    _,reaction,code=c.data.split(':',2); p=await get_pool()
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
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
