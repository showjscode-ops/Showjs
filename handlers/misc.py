from aiogram import Router,F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import html
from database import get_pool
from utils.economy import checkin
from config import CODE_GROUP_URL, NOTICE_CHANNEL_URL, CODE_GROUP_TITLE, NOTIF_CHANNEL_ID, BOT_USERNAME, CREATOR_ADMIN_ID

from utils.callback_loading import loading
router=Router()

def _code_link(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={code}"

def _safe_url(s: str) -> str:
    return html.escape(s, quote=True)

@router.callback_query(F.data=='creator_apply')
async def creator_apply(c):
    await loading(c)
    admin_url=f"tg://user?id={int(CREATOR_ADMIN_ID)}" if CREATOR_ADMIN_ID else ""
    text=(
        "👑 <b>PROGRAM KREATOR</b>\n\n"
        "Jadilah kreator dan buat CODE berbayar dari media kamu.\n\n"
        "💰 <b>Biaya pendaftaran: Rp200.000</b>\n\n"
        "📋 <b>Persyaratan & skema pengembalian:</b>\n"
        "• Periode evaluasi: 1 bulan sejak pendaftaran.\n"
        "• Jika berhasil menarik <b>200 member</b>: pengembalian/komisi pendaftaran <b>20%</b>.\n"
        "• Jika berhasil menarik <b>500 member</b>: pengembalian/komisi pendaftaran <b>50%</b>.\n"
        "• Jika berhasil menarik <b>1.000 member</b>: pengembalian/komisi pendaftaran <b>100%</b>.\n"
        "• Jika target belum tercapai dalam periode tersebut, kamu dapat menghubungi admin untuk meminta/menanyakan persyaratan dan periode berikutnya.\n\n"
        "⚠️ <b>Catatan:</b> target dan pengembalian mengikuti verifikasi admin.\n\n"
        "Tekan <b>Join Kreator</b> untuk menghubungi admin dan proses pendaftaran."
    )
    kb=[]
    if admin_url:
        kb.append([InlineKeyboardButton(text="👑 Join Kreator",url=admin_url)])
    kb.append([InlineKeyboardButton(text="🔙 Kembali",callback_data="menu_lainnya")])
    await c.message.edit_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


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
    rows=await (await get_pool()).fetch(
        "SELECT code,title,media_count,views,likes,hates,favorites FROM files "
        "WHERE owner_id=$1 AND active=TRUE ORDER BY id DESC LIMIT 30", c.from_user.id
    )
    text='📋 <b>MY CODE</b>\n\n'
    kb=[]
    if rows:
        for r in rows:
            title=html.escape((r['title'] or 'Untitled')[:45])
            text += f"📝 <b>{title}</b>\n🔑 <code>{html.escape(r['code'])}</code> • {r['media_count']} media\n"
            text += f"👁 {r['views']} • 👍 {r['likes']} • 👎 {r['hates']} • ⭐ {r['favorites']}\n\n"
            kb.append([InlineKeyboardButton(text=f"📝 {title}", callback_data=f"browsecode:{r['code']}")])
    else:
        text+='Belum ada code.'
    kb.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')])
    await loading(c)
    await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def _all_codes_page(page:int=0, per_page:int=10):
    p=await get_pool()
    offset=max(0,page)*per_page
    rows=await p.fetch(
        "SELECT code,title,media_count,views,likes,hates,favorites,price_idr "
        "FROM files WHERE active=TRUE ORDER BY id DESC LIMIT $1 OFFSET $2",
        per_page, offset
    )
    total=await p.fetchval("SELECT COUNT(*) FROM files WHERE active=TRUE")
    return rows,int(total or 0)

def _code_list_kb(rows,page,total,per_page=10):
    kb=[]
    for r in rows:
        title=(r['title'] or 'Untitled')[:45]
        kb.append([InlineKeyboardButton(text=f"📝 {title}",url=_code_link(r['code']))])
    nav=[]
    pages=max(1,(total+per_page-1)//per_page)
    if page>0: nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'codepage:{page-1}'))
    nav.append(InlineKeyboardButton(text=f'📄 {page+1}/{pages}',callback_data='noop'))
    if page<pages-1: nav.append(InlineKeyboardButton(text='➡️',callback_data=f'codepage:{page+1}'))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def _render_all_codes(c,page=0,edit=False):
    rows,total=await _all_codes_page(page)
    text='🔑 <b>ALL CODE</b>\n\n'
    if not rows:
        text+='Belum ada code yang dibuat.'
    else:
        for r in rows:
            title=html.escape((r['title'] or 'Untitled')[:50])
            price=int(r['price_idr'] or 0)
            paid=f" • 💰 Rp{price:,}".replace(',','.') if price else " • 🆓"
            text += f"📝 <b>{title}</b>{paid}\n"
            text += f"👁 {r['views']} • 👍 {r['likes']} • 👎 {r['hates']} • ⭐ {r['favorites']}\n\n"
        text += "Klik <b>Judul</b> untuk mencari/membuka media yang terhubung dengan CODE tersebut."
    kb=_code_list_kb(rows,page,total)
    if edit:
        await c.message.edit_text(text,parse_mode='HTML',reply_markup=kb)
    else:
        await c.message.answer(text,parse_mode='HTML',reply_markup=kb)

@router.callback_query(F.data=='code_all')
async def code_all(c):
    await loading(c)
    await _render_all_codes(c,0,edit=True)

@router.callback_query(F.data.startswith('codepage:'))
async def codepage(c):
    await loading(c)
    try: page=int(c.data.split(':',1)[1])
    except: page=0
    await _render_all_codes(c,page,edit=True)

@router.callback_query(F.data.startswith('browsecode:'))
async def browsecode(c):
    await loading(c)
    code=c.data.split(':',1)[1]
    p=await get_pool()
    f=await p.fetchrow(
        "SELECT code,title,media_count,views,likes,hates,favorites,price_idr "
        "FROM files WHERE lower(code)=lower($1) AND active=TRUE", code
    )
    if not f:
        return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    price=int(f['price_idr'] or 0)
    paid=f"💰 Harga: <b>Rp{price:,}</b>".replace(',','.') if price else "🆓 <b>FREE CODE</b>"
    await c.message.edit_text(
        f"📝 <a href=\"{_safe_url(_code_link(f['code']))}\"><b>{html.escape(f['title'] or 'Untitled')}</b></a>\n\n"
        f"🔑 <code>{html.escape(f['code'])}</code>\n"
        f"📦 Media: <b>{f['media_count']}</b>\n{paid}\n\n"
        f"👁 Total View: <b>{f['views']}</b>\n"
        f"👍 Total Like: <b>{f['likes']}</b>\n"
        f"👎 Total Hate: <b>{f['hates']}</b>\n"
        f"⭐ Total Favorit: <b>{f['favorites']}</b>\n\n"
        "Klik <b>Buka Code</b> untuk mencari dan membuka media yang terhubung.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📥 Buka Code',callback_data=f'getcode:{f["code"]}')],
            [InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{f["code"]}'),
             InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{f["code"]}'),
             InlineKeyboardButton(text='⭐ Favorit',callback_data=f'react:favorite:{f["code"]}')],
            [InlineKeyboardButton(text='🔙 Semua Code',callback_data='code_all')]
        ])
    )

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

@router.message(F.chat.type=='private', F.text, ~F.text.startswith('/'))
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
