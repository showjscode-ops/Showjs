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
    kb.append([InlineKeyboardButton(text="💳 Bayar Pendaftaran Rp200.000",callback_data="creator_buy")])
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


async def _paged_codes(page:int=0, mode:str="all", per_page:int=10):
    p=await get_pool()
    page=max(0,int(page)); offset=page*per_page
    if mode=="top":
        order="views DESC, likes DESC, favorites DESC, id DESC"
    elif mode=="recommend":
        order="(likes*3 + favorites*2 + views) DESC, views DESC, id DESC"
    else:
        order="id DESC"
    rows=await p.fetch(f"""
        SELECT id,code,title,media_count,views,likes,hates,favorites,price_idr
        FROM files WHERE active=TRUE ORDER BY {order} LIMIT $1 OFFSET $2
    """,per_page,offset)
    total=int(await p.fetchval("SELECT COUNT(*) FROM files WHERE active=TRUE") or 0)
    return rows,total

def _code_link(code):
    return f"https://t.me/Jsshowbot?start={code}"

def _code_text_row(r, prefix=""):
    title=html.escape((r['title'] or 'Untitled')[:60])
    href=html.escape(_code_link(r['code']),quote=True)
    price=int(r['price_idr'] or 0)
    paid=f" • 💰 Rp{price:,}".replace(',','.') if price else " • 🆓"
    return (
        f"{prefix}<a href=\"{href}\">📝 {title}</a>{paid}\n"
        f"👁 {r['views']} • 👍 {r['likes']} • 👎 {r['hates']} • ⭐ {r['favorites']}\n\n"
    )

def _code_nav(page,total,mode):
    pages=max(1,(total+9)//10)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'{mode}page:{page-1}'))
    nav.append(InlineKeyboardButton(text=f'📄 {page+1}/{pages}',callback_data='noop'))
    if page<pages-1: nav.append(InlineKeyboardButton(text='➡️',callback_data=f'{mode}page:{page+1}'))
    rows=[nav]
    if mode=="all":
        rows.append([
            InlineKeyboardButton(text='🔝 Top 10',callback_data='top_codes'),
            InlineKeyboardButton(text='⭐ Recommendation',callback_data='recommendation')
        ])
    elif mode=="top":
        rows.append([InlineKeyboardButton(text='⭐ Recommendation',callback_data='recommendation'),
                     InlineKeyboardButton(text='🔑 All Code',callback_data='code_all')])
    else:
        rows.append([InlineKeyboardButton(text='🔝 Top 10',callback_data='top_codes'),
                     InlineKeyboardButton(text='🔑 All Code',callback_data='code_all')])
    rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _render_code_list(c,page=0,mode="all"):
    rows,total=await _paged_codes(page,mode,10)
    heading={"all":"🔑 <b>ALL CODE</b>","top":"🔝 <b>TOP 10 CODE</b>","recommend":"⭐ <b>RECOMMENDATION</b>"}[mode]
    text=heading+"\n\n"
    if not rows:
        text+="Belum ada code yang dibuat."
    else:
        for i,r in enumerate(rows, page*10+1):
            text+=_code_text_row(r, f"{i}. " if mode!="all" else "")
        text+="Klik <b>Judul</b> untuk mencari/membuka media yang terhubung dengan CODE tersebut."
    await c.message.edit_text(text,parse_mode='HTML',reply_markup=_code_nav(page,total,mode))

@router.callback_query(F.data=='code_all')
async def code_all(c):
    await loading(c); await _render_code_list(c,0,"all")

@router.callback_query(F.data.startswith('codepage:'))
async def codepage(c):
    await loading(c)
    try: page=int(c.data.split(':',1)[1])
    except: page=0
    await _render_code_list(c,page,"all")

@router.callback_query(F.data=='top_codes')
async def top_codes(c):
    await loading(c); await _render_code_list(c,0,"top")

@router.callback_query(F.data.startswith('toppage:'))
async def toppage(c):
    await loading(c)
    try: page=int(c.data.split(':',1)[1])
    except: page=0
    await _render_code_list(c,page,"top")

@router.callback_query(F.data=='recommendation')
async def recommendation(c):
    await loading(c); await _render_code_list(c,0,"recommend")

@router.callback_query(F.data.startswith('recommendpage:'))
async def recommendpage(c):
    await loading(c)
    try: page=int(c.data.split(':',1)[1])
    except: page=0
    await _render_code_list(c,page,"recommend")

@router.callback_query(F.data.startswith('browsecode:'))
async def browsecode(c):
    await loading(c)
    code=c.data.split(':',1)[1]
    p=await get_pool()
    f=await p.fetchrow("SELECT code,title,media_count,views,likes,hates,favorites,price_idr FROM files WHERE lower(code)=lower($1) AND active=TRUE", code)
    if not f: return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
    price=int(f['price_idr'] or 0)
    paid=f"💰 Harga: <b>Rp{price:,}</b>".replace(',','.') if price else "🆓 <b>FREE CODE</b>"
    href=html.escape(_code_link(f['code']),quote=True)
    await c.message.edit_text(
        f"📝 <a href=\"{href}\"><b>{html.escape(f['title'] or 'Untitled')}</b></a>\n\n"
        f"🔑 <code>{html.escape(f['code'])}</code>\n📦 Media: <b>{f['media_count']}</b>\n{paid}\n\n"
        f"👁 Total View: <b>{f['views']}</b>\n👍 Total Like: <b>{f['likes']}</b>\n👎 Total Hate: <b>{f['hates']}</b>\n⭐ Total Favorit: <b>{f['favorites']}</b>\n\n"
        "Klik <b>Judul</b> untuk mencari/membuka media yang terhubung dengan CODE tersebut.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='👍 Like',callback_data=f'react:like:{f["code"]}'),
             InlineKeyboardButton(text='👎 Hate',callback_data=f'react:hate:{f["code"]}'),
             InlineKeyboardButton(text='⭐ Favorit',callback_data=f'react:favorite:{f["code"]}')],
            [InlineKeyboardButton(text='🔙 Semua Code',callback_data='code_all')]
        ])
    )

HELP_TEXTS={
"id":"""❓ <b>PANDUAN LENGKAP</b>

📤 <b>Up File</b>
Kirim media melalui menu Up File. Bot menyimpan media ke storage dan membuat CODE. Setelah itu kamu dapat mengisi judul, tag, dan harga.

📥 <b>Get File</b>
Masukkan CODE atau buka judul CODE. Untuk FREE CODE kamu dapat membuka media dengan Poin atau Star. Paid Code dapat dibayar melalui Saldo/QR sesuai metode yang aktif.

🪙 <b>Poin</b>
Poin digunakan untuk membuka FREE CODE. Akses Poin berlaku 24 jam. Creator mendapat potongan biaya Poin sesuai aturan bot.

⭐ <b>Star</b>
Star digunakan untuk membuka FREE CODE dan akses berlaku 48 jam.

💎 <b>VIP</b>
VIP dapat membuka media tanpa membayar per CODE. Code yang sama memiliki jeda pembukaan sesuai aturan VIP.

💳 <b>Pembayaran</b>
BayarGG/Cashi menampilkan QR. Setelah membayar tekan Cek Pembayaran. Jika batal, QR dihapus. Pembayaran manual membutuhkan screenshot bukti dan persetujuan admin.

🎁 <b>Check In</b>
Check-in setiap hari untuk mendapatkan Poin. Hari 1–6 mendapat 0.1 Poin dan hari ke-7 mendapat 1 Poin.

👑 <b>Creator</b>
Creator dapat membuat CODE berbayar. Pendaftaran dan verifikasi mengikuti aturan yang tampil di menu Creator.

🔑 <b>All Code / Top 10 / Recommendation</b>
Judul CODE dapat langsung diklik untuk membuka bot @Jsshowbot dengan CODE tersebut. Gunakan tombol halaman untuk melihat daftar berikutnya.

🆘 <b>Masih bingung?</b>
Kembali ke Dashboard lalu buka Help kapan saja.""",
"en":"""❓ <b>FULL GUIDE</b>

📤 <b>Up File</b>
Send your media from Up File. The bot stores the media and creates a CODE. You can then set the title, tags, and price.

📥 <b>Get File</b>
Enter a CODE or click a CODE title. For FREE CODE, media can be unlocked with Points or Stars. Paid Code can be purchased using Balance or an enabled QR payment method.

🪙 <b>Points</b>
Points are used to unlock FREE CODE media. Point access lasts 24 hours. Creators receive the configured Point benefit.

⭐ <b>Stars</b>
Stars can unlock FREE CODE media. Star access lasts 48 hours.

💎 <b>VIP</b>
VIP users can open media without paying for each CODE. The same CODE has a VIP cooldown according to the bot rules.

💳 <b>Payments</b>
BayarGG/Cashi shows a QR. After paying, press Check Payment. If you cancel, the QR message is removed. Manual payment requires a screenshot and admin approval.

🎁 <b>Check In</b>
Check in daily to receive Points. Days 1–6 give 0.1 Point and day 7 gives 1 Point.

👑 <b>Creator</b>
Creators can make paid CODEs. Registration and verification follow the rules shown in the Creator menu.

🔑 <b>All Code / Top 10 / Recommendation</b>
CODE titles are directly clickable and open @Jsshowbot with the CODE. Use the page buttons to browse more.

🆘 <b>Still confused?</b>
Return to Dashboard and open Help anytime.""",
"zh":"""❓ <b>完整使用说明</b>

📤 <b>上传文件 Up File</b>
进入 Up File 发送媒体。机器人会保存媒体并生成 CODE。之后可以设置标题、标签和价格。

📥 <b>获取文件 Get File</b>
输入 CODE 或点击 CODE 标题。FREE CODE 可以使用 Poin 或 Star 解锁，付费 CODE 可以使用余额或已开启的二维码支付方式购买。

🪙 <b>Poin</b>
Poin 用于解锁 FREE CODE，使用有效期为 24 小时。

⭐ <b>Star</b>
Star 用于解锁 FREE CODE，使用有效期为 48 小时。

💎 <b>VIP</b>
VIP 可以按照机器人规则打开媒体，同一个 CODE 有冷却时间。

💳 <b>付款</b>
BayarGG/Cashi 会显示二维码。付款后点击“检查付款”。取消付款后二维码消息会被删除。人工付款需要发送付款截图并等待管理员审核。

🎁 <b>每日签到</b>
每天签到获得 Poin。第 1–6 天每天 0.1 Poin，第 7 天获得 1 Poin。

👑 <b>Creator 创作者</b>
Creator 可以创建付费 CODE。注册和审核按照 Creator 页面显示的规则进行。

🔑 <b>All Code / Top 10 / Recommendation</b>
CODE 标题可以直接点击，会打开 @Jsshowbot 并携带对应 CODE。使用分页按钮浏览更多内容。

🆘 <b>仍然不明白？</b>
返回 Dashboard，随时打开 Help 查看说明。"""
}

@router.callback_query(F.data=='help')
async def help_(c):
    await loading(c)
    await c.message.edit_text(
        HELP_TEXTS["id"],parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🇮🇩 Indonesia',callback_data='help:lang:id'),
             InlineKeyboardButton(text='🇬🇧 English',callback_data='help:lang:en'),
             InlineKeyboardButton(text='🇨🇳 中文',callback_data='help:lang:zh')],
            [InlineKeyboardButton(text='🌐 Select Language / 选择语言',callback_data='help:lang:id')],
            [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
        ])
    )

@router.callback_query(F.data.startswith('help:lang:'))
async def help_lang(c):
    lang=c.data.rsplit(':',1)[1]
    if lang not in HELP_TEXTS: lang="id"
    await loading(c)
    await c.message.edit_text(
        HELP_TEXTS[lang],parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🇮🇩 Indonesia',callback_data='help:lang:id'),
             InlineKeyboardButton(text='🇬🇧 English',callback_data='help:lang:en'),
             InlineKeyboardButton(text='🇨🇳 中文',callback_data='help:lang:zh')],
            [InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]
        ])
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
