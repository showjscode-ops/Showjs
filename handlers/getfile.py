
from __future__ import annotations
import html,json,os,tempfile,asyncio
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,InputMediaPhoto,InputMediaVideo,InputMediaDocument,InputMediaAudio,BufferedInputFile
from database import get_pool
from utils.economy import unlock,is_creator,is_vip,vip_allowed
from utils.media_sender import deliver_one
from utils.notify_channel import notify
from utils.callback_loading import loading
from config import STAR_PER_MEDIA,MEDIA_SEND_DELAY_MS
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

@router.message(F.text.regexp(r'^[A-Za-z0-9]+_[123456789XxYy]{11}_[0-9]+p[0-9]+v[0-9]+d$'))
async def receive(m):
    await show(m,m.text.strip())

@router.callback_query(F.data.startswith('getcode:'))
async def getcode(c):
    await loading(c); code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    await c.answer()
    await (await get_pool()).execute("UPDATE files SET views=views+1 WHERE code=$1", code)
    await open_choices(c,code,f)

async def open_choices(c,code,f):
    uid=c.from_user.id; n=int(f['media_count']); price=int(f['price_idr'] or 0)
    if await is_vip(uid):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💎 Buka Gratis (VIP)',callback_data=f'openvip:{code}')],[InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]])
    elif price>0:
        rows=[]
        if await enabled('payment_balance'): rows.append([InlineKeyboardButton(text=f'💰 Saldo • {fmt(price)}',callback_data=f'openbal:{code}')])
        if await enabled('bayargg'): rows.append([InlineKeyboardButton(text='⚡ BayarGG QR',callback_data=f'payfile:bayargg:{code}')])
        if await enabled('cashi'): rows.append([InlineKeyboardButton(text='💳 Cashi QR',callback_data=f'payfile:cashi:{code}')])
        if await enabled('manual'): rows.append([InlineKeyboardButton(text='🧾 QR Manual',callback_data=f'payfile:manual:{code}')])
        rows.append([InlineKeyboardButton(text='💳 Deposit',callback_data='deposit')])
        kb=InlineKeyboardMarkup(inline_keyboard=rows)
    else:
        creator=await is_creator(uid); pc=n*0.5 if creator else n; sc=n*STAR_PER_MEDIA
        kb=InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text=f'🪙 {pc:g} Poin',callback_data=f'unlockp:{code}')],
          [InlineKeyboardButton(text=f'⭐ {sc:g} Star',callback_data=f'unlocks:{code}')],
          [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]])
    await c.message.edit_text(
      f"🔐 <b>OPEN CODE</b>\n\n📝 {html.escape(f['title'] or 'Untitled')}\n🔑 <code>{html.escape(code)}</code>\n📦 {n} media\n"
      +(f"💰 {fmt(price)}\n\nPilih pembayaran:" if price else "\nPilih cara membuka:"),
      parse_mode='HTML',reply_markup=kb)

async def _download_item(bot,item):
    from utils.b2_storage import b2_pool
    path,meta=await b2_pool.download(int(item['drive_account']),str(item['drive_file_id']))
    return path,meta

async def send_page(bot,chat_id,code,media,page):
    start=page*10; chunk=media[start:start+10]
    paths=[]; group=[]
    try:
        for i,item in enumerate(chunk,start+1):
            path,_=await _download_item(bot,item); paths.append(path)
            cap=f"🔑 {code}\n📄 Media {i}/{len(media)}\n📑 Page {page+1}"
            typ=item.get('type')
            inp=BufferedInputFile(open(path,'rb').read(),filename=item.get('file_name') or f'media-{i}')
            if typ=='photo': group.append(InputMediaPhoto(media=inp,caption=cap))
            elif typ=='video': group.append(InputMediaVideo(media=inp,caption=cap,supports_streaming=True))
            elif typ=='document': group.append(InputMediaDocument(media=inp,caption=cap))
            elif typ=='audio': group.append(InputMediaAudio(media=inp,caption=cap))
        # Telegram albums support 2-10 items, but media type mixing is restricted.
        if len(group)>=2 and all(isinstance(x,(InputMediaPhoto,InputMediaVideo)) for x in group):
            await bot.send_media_group(chat_id,media=group)
        elif len(group)>=2 and all(isinstance(x,InputMediaDocument) for x in group):
            await bot.send_media_group(chat_id,media=group)
        elif len(group)>=2 and all(isinstance(x,InputMediaAudio) for x in group):
            await bot.send_media_group(chat_id,media=group)
        else:
            for item in chunk:
                try: await deliver_one(bot,chat_id,item,caption=f"🔑 {code}\n📄 Media\n📑 Page {page+1}")
                except Exception: pass
        delay=MEDIA_SEND_DELAY_MS
        try: delay=int(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='media_send_delay_ms'") or delay)
        except: pass
        await asyncio.sleep(max(0,delay)/1000)
    finally:
        for path in paths:
            try: os.remove(path)
            except: pass

def page_kb(code,page,total):
    rows=[
      [InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{code}'),InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{code}'),InlineKeyboardButton(text='⭐ Favorit',callback_data=f'react:favorite:{code}')]
    ]
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'page:{code}:{page-1}'))
    nav.append(InlineKeyboardButton(text=f'📄 {page+1}/{(total+9)//10}',callback_data='noop'))
    if page<(total+9)//10-1: nav.append(InlineKeyboardButton(text='➡️',callback_data=f'page:{code}:{page+1}'))
    if nav: rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def deliver_page(c,code,page):
    f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    media=f['media'] if isinstance(f['media'],list) else json.loads(f['media'] or '[]')
    await send_page(c.bot,c.from_user.id,code,media,page)
    await c.message.answer(
      f"📄 <b>Page {page+1}/{(len(media)+9)//10}</b>\n\n"
      "Share this code with your friends to let them unlock these media.",
      parse_mode='HTML',reply_markup=page_kb(code,page,len(media)))

async def open_media(c,method):
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    price=int(f['price_idr'] or 0)
    if price>0:return await c.answer('Paid code menggunakan Saldo atau pembayaran QR.',show_alert=True)
    ok,new,reason,cost=await unlock(c.from_user.id,code,int(f['media_count']),method)
    if not ok:
        msg={'insufficient':'❌ Saldo tidak cukup.','cooldown':'⏳ VIP harus menunggu 30 menit sebelum membuka code ini lagi.'}.get(reason,'❌ Tidak dapat membuka media.')
        return await c.answer(msg,show_alert=True)
    await c.answer('✅ Berhasil dibuka!')
    await deliver_page(c,code,0)

@router.callback_query(F.data.startswith('openvip:'))
async def openvip(c):
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    ok,_,reason,_=await unlock(c.from_user.id,code,int(f['media_count']),'balance')
    if not ok:return await c.answer('⏳ VIP harus menunggu 30 menit sebelum membuka code ini lagi.',show_alert=True) if reason=='cooldown' else await c.answer('❌ Tidak dapat membuka.',show_alert=True)
    await deliver_page(c,code,0)

@router.callback_query(F.data.startswith('unlockp:'))
async def up(c): await open_media(c,'points')
@router.callback_query(F.data.startswith('unlocks:'))
async def us(c): await open_media(c,'star')

@router.callback_query(F.data.startswith('openbal:'))
async def openbal(c):
    code=c.data.split(':',1)[1]; f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    ok,_,reason,_=await unlock(c.from_user.id,code,int(f['media_count']),'balance')
    if not ok:return await c.answer('❌ Saldo tidak cukup.',show_alert=True)
    await c.answer('✅ Pembayaran berhasil!')
    await deliver_page(c,code,0)

@router.callback_query(F.data.startswith('payfile:'))
async def payfile(c,state):
    _,provider,code=c.data.split(':',2); f=await get_file(code)
    if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    if provider=='manual':
        qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
        if not qr:return await c.answer('❌ QR manual belum dipasang admin.',show_alert=True)
        await c.message.answer_photo(qr,caption=f"🧾 <b>QR MANUAL</b>\n\n💰 {fmt(f['price_idr'])}\n\nAfter payment, send your payment proof.",parse_mode='HTML')
        # Store the target code so admin approval opens this paid code directly.
        from aiogram.fsm.context import FSMContext
        # The callback handler can access FSM storage through dispatcher only in handler data;
        # use a short-lived per-user table row instead.
        p=await get_pool()
        await p.execute("INSERT INTO manual_deposits(user_id,amount,target_code,status) VALUES($1,$2,$3,'pending')",c.from_user.id,int(f['price_idr']),code)
        did=await p.fetchval("SELECT currval(pg_get_serial_sequence('manual_deposits','id'))")
        await state.set_state(ManualProofState.proof)
        await state.update_data(kind='file',amount=int(f['price_idr']),target_code=code)
        await c.message.answer(f"🧾 Payment ID: <code>{did}</code>\nSend screenshot of your payment proof.",parse_mode='HTML')
        return
    r,status=await create_purchase(c.from_user.id,'file',1,int(f['price_idr']),provider,c.from_user.full_name,{"code":code})
    if not r:return await c.answer('❌ Provider sedang ditutup.',show_alert=True)
    data=qr_bytes(r.get('qr_string'))
    text=f"💳 <b>PAYMENT</b>\n\n🔑 Code: <code>{code}</code>\n💰 {fmt(f['price_idr'])}\n🏦 {provider.upper()}\n\nPayment will be verified automatically."
    if data: await c.message.answer_photo(BufferedInputFile(data,filename='payment.png'),caption=text,parse_mode='HTML')
    else: await c.message.answer(text,parse_mode='HTML')

@router.callback_query(F.data.startswith('page:'))
async def page(c):
    _,code,pg=c.data.split(':',2); await loading(c); await deliver_page(c,code,int(pg))

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
