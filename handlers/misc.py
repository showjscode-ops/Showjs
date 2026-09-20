from aiogram import Router,F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import html
from database import get_pool
from utils.economy import checkin
from config import CODE_GROUP_ID, CODE_GROUP_URL, NOTICE_CHANNEL_URL, CODE_GROUP_TITLE, NOTIF_CHANNEL_ID, BOT_USERNAME, CREATOR_ADMIN_ID

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
"id":"""PANDUAN LENGKAP

UP FILE
Kirim media melalui menu Up File di chat pribadi dengan bot. Bot akan menyimpan media, membuat CODE, dan menyimpan cadangan Telegram file_id. Creator dan Admin dapat membuat Paid Code. User biasa mengikuti batas akses yang berlaku.

GET FILE
Masukkan CODE atau tekan tombol GET FILE. Media selalu dikirim ke chat pribadi, bukan ke group. Jika media di storage utama tidak tersedia, bot akan mencoba cadangan Telegram file_id. Jika semua sumber tidak tersedia, media tersebut akan ditandai tidak tersedia.

FREE CODE
Free Code dapat dibuka sesuai metode akses yang tersedia, seperti Poin, Star, VIP, atau aturan akun. Masa akses mengikuti metode yang digunakan.

PAID CODE
Paid Code memiliki harga yang ditentukan oleh pembuat Code. Harga Paid mulai dari Rp2.000 sesuai aturan sistem. Saat pembayaran QR dipilih, nominal QR otomatis mengikuti harga Code.

PEMBAYARAN QR
QR 1 = Cashi.
QR 2 = BayarGG.
Nama penyedia pembayaran tidak ditampilkan sebagai nama metode kepada pengguna; bot menggunakan nama QR 1 dan QR 2.

Jika nominal Code di bawah batas QR 2, sistem dapat mengalihkan pembayaran ke QR 1. Jika QR 1 juga tidak tersedia atau tidak mendukung nominal tersebut, sistem menggunakan QR Manual jika admin telah memasangnya.

QR Manual
QR Manual digunakan sebagai metode cadangan. User membayar sesuai nominal Code, lalu mengirim bukti pembayaran. Admin memeriksa bukti dan dapat menyetujui atau menolak pembayaran. Akses diberikan setelah pembayaran disetujui.

SALDO
Pembayaran menggunakan Saldo digunakan untuk akses Paid Code sesuai aturan sistem. Akses yang dibeli menggunakan Saldo dapat dipertahankan secara permanen sesuai aturan akses permanen.

POIN
Poin adalah saldo poin untuk fitur yang mendukung pembayaran dengan Poin. Poin dapat diperoleh dari aktivitas bot, Check In, transaksi, atau paket Poin sesuai aturan yang aktif. Jumlah Poin yang diperlukan mengikuti jenis media dan status akun.

CREATOR
Creator dapat membuat dan menjual Paid Code.
Creator wajib melakukan upload Paid setiap hari sesuai aturan Creator.
Kuota dasar Creator untuk membuka Paid Code adalah 1 kali per hari.
Setiap 10 member unik yang membeli Paid Code Creator memberikan tambahan 1 kesempatan pembukaan Paid Code per hari.
Creator mendapatkan manfaat Poin sesuai persentase yang ditetapkan sistem.
Pendapatan Creator mengikuti pembagian komisi yang berlaku di platform.
Creator yang pernah menjadi Creator dapat mengikuti mekanisme pembayaran lanjutan sebesar 30 persen dari biaya pendaftaran sesuai aturan sistem.

VIP
VIP adalah status berlangganan yang memberikan akses dan keuntungan sesuai paket VIP yang dibeli.
Benefit, durasi, cooldown, dan batas akses mengikuti paket VIP yang aktif. Detail paket dapat dilihat pada menu Buy VIP.

STAR
Star adalah saldo Star yang digunakan pada fitur yang mendukung Star.
Star dapat digunakan untuk membuka media sesuai aturan Star. Ketentuan durasi akses dan penggunaan mengikuti konfigurasi sistem yang aktif.

CHECK IN
Check In dapat digunakan setiap hari untuk memperoleh Poin sesuai aturan check-in. Reward dan ketentuan streak mengikuti konfigurasi yang aktif.

GROUP CODE
Jika user mengirim CODE di group khusus, bot dapat mendeteksi CODE dan menampilkan notifikasi teks serta tombol GET FILE.
Tombol tersebut hanya dapat digunakan oleh user yang sudah memulai chat dengan bot menggunakan /start. User lain yang belum /start akan diminta melakukan /start terlebih dahulu.
Media tidak pernah dikirim ke group. Media hanya dikirim ke private chat user yang melakukan akses.

MEDIA EXPIRED
Media dengan akses sementara dapat memiliki masa berlaku. Jika masa akses telah berakhir, media dapat dihapus oleh sistem sesuai aturan expiry. Akses permanen tidak mengikuti penghapusan sementara sesuai aturan sistem.

KEAMANAN PEMBAYARAN
Jangan mengirim bukti pembayaran palsu. Jangan membagikan QR, invoice, atau data pembayaran kepada pihak lain. Jika pembayaran berhasil tetapi akses belum terbuka, hubungi Admin melalui jalur bantuan yang tersedia.

ADMIN
Admin dapat mengelola user, status akun, pembayaran manual, dan akses Code sesuai izin panel admin. Dalam kasus pembelian yang berhasil tetapi akses otomatis bermasalah, Admin dapat memberikan akses Code secara manual kepada user.

Jika masih bingung, kembali ke Dashboard dan buka Help kapan saja.""",

"en":"""FULL GUIDE

UP FILE
Send media through Up File in the bot's private chat. The bot stores the media, creates a CODE, and keeps a Telegram file_id backup. Creators and Admins can create Paid Codes. Regular users follow the access limits that apply to their accounts.

GET FILE
Enter a CODE or press GET FILE. Media is always delivered to the user's private chat, never to the group. If the primary storage is unavailable, the bot tries the Telegram file_id backup. If all sources are unavailable, that media is marked unavailable.

FREE CODE
Free Code can be opened through the available access methods such as Points, Stars, VIP, or account rules. The access period depends on the method used.

PAID CODE
A Paid Code has a price set by its creator. Paid prices start from Rp2,000 under the system rules. When a QR payment is selected, the QR amount automatically follows the Code price.

QR PAYMENTS
QR 1 = Cashi.
QR 2 = BayarGG.
Provider names are not shown as payment method names to users; the bot presents them as QR 1 and QR 2.

If the Code amount is below the QR 2 minimum, the system can move the payment to QR 1. If QR 1 is also unavailable or does not support the amount, the system uses QR Manual when the admin has configured it.

QR Manual
QR Manual is the fallback payment method. Pay the exact Code amount, then submit payment proof. An Admin reviews the proof and can approve or reject the payment. Access is granted after approval.

BALANCE
Balance payment is used for Paid Code access under the active access rules. Access purchased with Balance can be permanent when the permanent-access rule applies.

POINTS
Points are the point balance used by features that support Points. Points may be earned from bot activities, Check In, transactions, or Point packages according to the active rules. The required amount depends on the media type and account status.

CREATOR
Creators can create and sell Paid Codes.
Creators are required to upload Paid content every day under the Creator rules.
The base Creator allowance for opening Paid Code is 1 time per day.
Every 10 unique members who purchase a Creator's Paid Code gives 1 additional Paid Code opening per day.
Creators receive the configured Point benefit.
Creator earnings follow the platform's active commission rules.
A user who was previously a Creator can use the renewal mechanism at 30 percent of the registration fee according to the system rules.

VIP
VIP is a subscription status that provides access and benefits according to the purchased VIP package.
Benefits, duration, cooldowns, and limits follow the active VIP package. Open Buy VIP to view the available packages.

STAR
Stars are a Star balance used by features that support Stars.
Stars can be used to open media according to the Star rules. Access duration and usage follow the active system configuration.

CHECK IN
Check In can be used daily to receive Points according to the check-in rules. Rewards and streak conditions follow the active configuration.

GROUP CODE
When a user sends a CODE in the designated group, the bot can detect the CODE and post a text notification with a GET FILE button.
The button can only be used by a user who has already started a private chat with the bot using /start. Other users who have not started the bot are asked to use /start first.
Media is never sent to the group. Media is delivered only to the private chat of the user requesting access.

MEDIA EXPIRY
Temporary access can have an expiry period. When the access period ends, the media may be deleted by the expiry system. Permanent access follows the permanent-access rules.

PAYMENT SAFETY
Do not submit fake payment proof. Do not share QR, invoice, or payment data with other people. If payment succeeds but access does not open, contact Admin through the available support route.

ADMIN
Admins can manage users, account statuses, manual payments, and Code access according to panel permissions. If a successful purchase cannot automatically open access, an Admin can manually grant Code access to the user.

If you are still confused, return to Dashboard and open Help anytime.""",

"zh":"""完整使用说明

上传文件 UP FILE
请在机器人私聊中使用 Up File 发送媒体。机器人会保存媒体、生成 CODE，并保存 Telegram file_id 作为备用。Creator 和 Admin 可以创建付费 CODE，普通用户按照账号权限使用。

获取文件 GET FILE
输入 CODE 或点击 GET FILE。媒体始终发送到用户私聊，不会发送到群组。如果主要存储不可用，机器人会尝试使用 Telegram file_id 备用媒体。如果所有来源都不可用，该媒体会被标记为不可用。

免费 CODE
Free Code 可以根据当前可用的 Poin、Star、VIP 或账号规则打开。有效时间取决于所使用的方式。

付费 CODE
Paid Code 的价格由创建者设置。按照系统规则，Paid Code 最低从 Rp2,000 开始。选择二维码支付时，二维码金额会自动使用 CODE 的价格。

二维码支付
QR 1 = Cashi。
QR 2 = BayarGG。
用户界面不会显示支付平台名称，而是统一显示为 QR 1 和 QR 2。

如果 CODE 金额低于 QR 2 的最低金额，系统可以自动转到 QR 1。如果 QR 1 也不可用或不支持该金额，并且管理员已经设置了人工二维码，则系统会使用 QR Manual。

人工二维码 QR Manual
QR Manual 是备用支付方式。用户按照 CODE 的准确金额付款，然后提交付款截图。管理员审核截图后可以批准或拒绝。审核通过后才会开通访问权限。

余额 SALDO
使用余额支付可以按照当前规则打开 Paid Code。符合永久访问规则的余额购买可以保持永久访问。

积分 POIN
Poin 是支持积分功能时使用的积分余额。积分可以通过机器人活动、每日签到、交易或积分套餐获得。需要的积分数量取决于媒体类型和账号状态。

CREATOR
Creator 可以创建和销售 Paid Code。
Creator 按照规则每天必须上传 Paid 内容。
Creator 每天基础可以免费打开 Paid Code 1 次。
每有 10 个不同会员购买 Creator 的 Paid Code，每天增加 1 次 Paid Code 免费打开次数。
Creator 按系统设置获得 Poin 优惠。
Creator 收益按照平台当前的分成规则计算。
以前已经成为 Creator 的用户，可以按照系统规则以注册费用的 30% 使用续费或再次升级机制。

VIP
VIP 是一种会员订阅状态，可以根据购买的 VIP 套餐获得对应权限和福利。
具体福利、有效期、冷却时间和限制以当前 VIP 套餐为准。可以进入 Buy VIP 查看套餐。

STAR
Star 是支持 Star 功能时使用的 Star 余额。
Star 可以按照 Star 规则打开媒体。有效时间和使用规则以当前系统配置为准。

每日签到 CHECK IN
每天可以使用 Check In 获得 Poin。签到奖励和连续签到规则按照当前配置执行。

群组 CODE
当用户在指定群组发送 CODE 时，机器人可以识别 CODE，并在群组中发送文字通知和 GET FILE 按钮。
只有已经使用 /start 与机器人建立私聊的用户才能使用该按钮。其他未启动机器人的用户会被要求先使用 /start。
媒体绝不会发送到群组，只会发送到请求访问的用户私聊。

媒体过期
临时访问可以设置有效时间。访问时间结束后，媒体可能会由过期系统删除。永久访问按照永久访问规则处理。

支付安全
请勿提交虚假付款证明，也不要向他人分享二维码、发票或支付信息。如果付款成功但 CODE 没有打开，请通过可用的客服方式联系 Admin。

管理员 ADMIN
管理员可以根据后台权限管理用户、账号状态、人工付款和 CODE 访问。如果用户已经成功付款但自动开通失败，管理员可以在后台为指定用户手动开通 CODE。

如果仍然不明白，请返回 Dashboard，随时打开 Help 查看说明。"""
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

@router.message(F.chat.type == 'private', F.photo)
async def photo_hint(m): await media_hint(m)

@router.message(F.chat.type == 'private', F.video)
async def video_hint(m): await media_hint(m)

@router.message(F.chat.type == 'private', F.document)
async def document_hint(m): await media_hint(m)

@router.message(F.chat.type == 'private', F.audio)
async def audio_hint(m): await media_hint(m)

@router.message(F.chat.type.in_({'group','supergroup'}), F.chat.id == CODE_GROUP_ID, F.text.regexp(r'^[A-Za-z0-9]+_[123456789XxYy]{11}_[0-9]+p[0-9]+v[0-9]+d$'))
async def track_group_code(m):
    code=m.text.strip()
    p=await get_pool()
    row=await p.fetchrow("SELECT code FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)
    if not row:
        return
    try:
        await p.execute(
            "INSERT INTO code_group_shares(code,group_id,shared_by) VALUES($1,$2,$3) "
            "ON CONFLICT(code,group_id) DO UPDATE SET last_seen_at=NOW()",
            code,m.chat.id,m.from_user.id
        )
    except Exception:
        pass
    from utils.group_notify import notify_code_detected
    await notify_code_detected(m.bot, m, row["code"])

@router.callback_query(F.data.startswith('groupget:'))
async def group_get_file(c):
    # This callback originates in the group. It must NEVER send media to the group.
    # It only sends a private control message after the user has started the bot.
    code=c.data.split(':',1)[1].strip()
    p=await get_pool()
    started=await p.fetchval("SELECT bot_started_at FROM users WHERE user_id=$1",c.from_user.id)
    if not started:
        await c.answer("Klik /start dulu di bot. Setelah itu kamu bisa menekan GET FILE.", show_alert=True)
        return

    f=await p.fetchrow(
        "SELECT code,title,media_count,price_idr,active FROM files "
        "WHERE lower(code)=lower($1) AND active=TRUE",code
    )
    if not f:
        await c.answer("Code tidak ditemukan atau sudah tidak aktif.", show_alert=True)
        return

    from handlers.getfile import open_choices
    # Open the code in the user's private chat. A bot can only initiate this
    # because the user has already started the bot.
    try:
        await c.bot.send_message(
            c.from_user.id,
            f"CODE TERDETEKSI\n\n"
            f"Code: <code>{html.escape(f['code'])}</code>\n"
            f"Media: <b>{int(f['media_count'])}</b>\n\n"
            "Pilih GET FILE untuk melanjutkan.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="GET FILE", callback_data=f"getcode:{f['code']}")]
            ])
        )
        await c.answer("GET FILE dikirim ke chat pribadi.")
    except Exception:
        await c.answer("Buka chat pribadi dengan bot lalu klik /start.", show_alert=True)
