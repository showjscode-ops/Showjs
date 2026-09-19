from aiogram import Router,F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool
from utils.economy import checkin
from config import CODE_GROUP_URL, NOTICE_CHANNEL_URL, CODE_GROUP_TITLE, NOTIF_CHANNEL_ID, BOT_USERNAME

from utils.callback_loading import loading
router=Router()

@router.callback_query(F.data=='checkin')
async def ci(c):
    bal,day,ok=await checkin(c.from_user.id)
    await c.answer('Sudah check-in hari ini.' if not ok else f'+{1 if day==7 else 0.1} Poin')
    await c.message.edit_text(
        f'🎁 <b>CHECK IN</b>\n\n📅 Hari: <b>{day}/7</b>\n🪙 Saldo Poin: <b>{float(bal):g}</b>\n\nHari 1-6 = 0.1 Poin\nHari 7 = 1 Poin.',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')]])
    )

@router.callback_query(F.data=='my_code')
async def my(c):
    rows=await (await get_pool()).fetch("SELECT code,title,media_count FROM files WHERE owner_id=$1 ORDER BY id DESC LIMIT 30",c.from_user.id)
    text='📋 <b>MY CODE</b>\n\n'+(
        '\n'.join(f'🔑 <code>{r["code"]}</code> • {r["media_count"]} media\n📝 {r["title"] or "-"}' for r in rows)
        if rows else 'Belum ada code.'
    )
    await loading(c); await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')]]))

@router.callback_query(F.data=='group_code')
async def group(c):
    rows=await (await get_pool()).fetch("SELECT code,group_id FROM code_group_shares WHERE shared_by=$1 ORDER BY last_seen_at DESC LIMIT 30",c.from_user.id)
    text='👥 <b>GROUP CODE</b>\n\n'+(
        '\n'.join(f'🔑 <code>{r["code"]}</code> • {r["group_id"]}' for r in rows)
        if rows else 'Belum ada CODE yang terdeteksi di group.'
    )
    await loading(c); await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')]]))


@router.callback_query(F.data=='top_codes')
async def top_codes(c):
    rows=await (await get_pool()).fetch("""SELECT code,title,views,likes,hates,favorites,price_idr
      FROM files WHERE active=TRUE ORDER BY views DESC,likes DESC LIMIT 10""")
    text='🏆 <b>TOP 10 CODE</b>\n\n'
    if not rows:text+='Belum ada code.'
    else:
        for i,r in enumerate(rows,1):
            text+=f"{i}. <b>{html.escape(r['title'] or 'Untitled')}</b>\n🔑 <code>{r['code']}</code>\n👁 {r['views']} • 👍 {r['likes']} • 👎 {r['hates']} • ⭐ {r['favorites']}\n\n"
    await loading(c); await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]]))

@router.callback_query(F.data=='help')
async def help_(c):
    await loading(c)
    await c.message.edit_text(
        '❓ <b>HELP</b>\n\n📤 Up File → media otomatis ke Backblaze B2.\n📥 Get File → unlock dengan Poin atau Star.\n🪙 Poin → akses 24 jam.\n⭐ Star → akses 48 jam.\n👑 Creator → potongan Poin 50% dan +1 Poin setiap unlock berhasil.\n🎁 Check In → hari 1-6 = 0.1 Poin, hari 7 = 1 Poin.',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')]])
    )

@router.callback_query(F.data=='buy_vip')
async def vip(c):
    rows=await (await get_pool()).fetch("SELECT code,name,price,duration_days FROM vip_packages WHERE active ORDER BY price")
    kb=[[InlineKeyboardButton(text=f'💎 {r["name"]} • Rp{int(r["price"]):,}'.replace(',','.'),callback_data=f'vip:{r["code"]}')] for r in rows]
    kb.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
    await loading(c); await c.message.edit_text('💎 <b>BUY VIP</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

def quick_links():
    rows=[]
    if CODE_GROUP_URL:
        rows.append([InlineKeyboardButton(text=f'👥 {CODE_GROUP_TITLE}',url=CODE_GROUP_URL)])
    elif NOTIF_CHANNEL_ID:
        rows.append([InlineKeyboardButton(text='👥 Group Chat Code',callback_data='open_group_info')])
    if NOTICE_CHANNEL_URL:
        rows.append([InlineKeyboardButton(text='🔔 Channel Notifikasi',url=NOTICE_CHANNEL_URL)])
    elif NOTIF_CHANNEL_ID:
        rows.append([InlineKeyboardButton(text='🔔 Channel Notifikasi',callback_data='open_notice_info')])
    return rows

@router.callback_query(F.data=='open_group_info')
async def open_group_info(c):
    await c.answer('Group Chat Code belum dikonfigurasi URL-nya.',show_alert=True)

@router.callback_query(F.data=='open_notice_info')
async def open_notice_info(c):
    await c.answer('Channel Notifikasi belum dikonfigurasi URL-nya.',show_alert=True)

@router.message(F.chat.type=='private', F.text)
async def keyword_help(m:Message):
    text=(m.text or '').strip().lower()
    if text in {'group','vip','video'}:
        rows=quick_links()
        await m.answer('🔗 <b>LINK BOT</b>\n\nPilih tujuan yang kamu perlukan:',parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text='🏠 Menu',callback_data='home')]]))
        return
    if text in {'poin','point','points'}:
        p=await get_pool(); bal=await p.fetchval('SELECT points FROM users WHERE user_id=$1',m.from_user.id) or 0
        await m.answer(f'🪙 <b>Poin kamu sekarang: {float(bal):g}</b>',parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🛒 Buy Poin',callback_data='buy_points')]]))
        return
    if text in {'star','stars'}:
        p=await get_pool(); bal=await p.fetchval('SELECT stars FROM users WHERE user_id=$1',m.from_user.id) or 0
        await m.answer(f'⭐ <b>Star kamu sekarang: {float(bal):g}</b>',parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🛒 Buy Star',callback_data='buy_stars')]]))

async def media_hint(m:Message):
    await m.answer('📎 <b>Media terdeteksi</b>\n\nTekan tombol di bawah untuk upload.',parse_mode='HTML',
                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📤 Up File',callback_data='upfile')]]))

@router.message(F.photo)
async def photo_hint(m): await media_hint(m)

@router.message(F.video)
async def video_hint(m): await media_hint(m)

@router.message(F.document)
async def document_hint(m): await media_hint(m)

@router.message(F.audio)
async def audio_hint(m): await media_hint(m)

@router.message(F.chat.type.in_({'group','supergroup'}), F.text.regexp(r'^[A-Za-z0-9]+_[123456789XxYy]{11}_[0-9]+p[0-9]+v[0-9]+d$'))
async def track_group_code(m):
    p=await get_pool(); code=m.text.strip()
    owner=await p.fetchval("SELECT owner_id FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)
    if owner:
        await p.execute("INSERT INTO code_group_shares(code,group_id,shared_by) VALUES($1,$2,$3) ON CONFLICT(code,group_id) DO UPDATE SET last_seen_at=NOW()",code,m.chat.id,m.from_user.id)
