from aiogram import Router,F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import html
import re
from decimal import Decimal
from database import get_pool
from utils.economy import checkin
from utils.i18n import get_lang
from config import CODE_GROUP_ID, CODE_GROUP_URL, NOTICE_CHANNEL_URL, CODE_GROUP_TITLE, NOTIF_CHANNEL_ID, BOT_USERNAME, CREATOR_ADMIN_ID, ALL_CODE_CHANNEL_URL, BACKUP_CHANNEL_URL

from utils.callback_loading import loading
router=Router()


# Direct Group & Channel links
DIRECT_GROUP_CODE_URL = "https://t.me/+WeFUnjG8ojQzOWQ5"
DIRECT_ALL_CODE_URL = "https://t.me/+NrHk5eHAiTFiNzc1"
DIRECT_BACKUP_URL = "https://t.me/+g3t3JY6ft8xhYTE1"
DIRECT_NOTICE_URL = "https://t.me/noticsaluran"

class TransferState(StatesGroup):
    username = State()
    amount = State()


async def _lang(uid: int) -> str:
    try:
        lang = await get_lang(uid)
        return lang if lang in UI_TEXT else "id"
    except Exception:
        return "id"

UI_TEXT = {
    "id": {
        "join_creator":"👑 Join Kreator", "pay_creator":"💳 Bayar Pendaftaran Rp200.000", "back":"🔙 Kembali",
        "creator_title":"👑 <b>PROGRAM KREATOR</b>", "creator_desc":"Jadilah kreator dan buat CODE berbayar dari media kamu.",
        "creator_req":"📋 <b>Persyaratan & skema pengembalian:</b>", "period":"• Periode evaluasi: 1 bulan sejak pendaftaran.",
        "target":"• Jika berhasil menarik <b>{n} member</b>: pengembalian/komisi pendaftaran <b>{p}%</b>.",
        "target_last":"• Jika target belum tercapai dalam periode tersebut, kamu dapat menghubungi admin untuk meminta/menanyakan persyaratan dan periode berikutnya.",
        "note":"⚠️ <b>Catatan:</b> target dan pengembalian mengikuti verifikasi admin.",
        "creator_contact":"• Hubungi admin jika perlu bantuan atau verifikasi.",
        "checkin_done":"Sudah check-in hari ini.", "checkin_reward":"+{x} Poin", "checkin":"🎁 <b>CHECK IN</b>\n\n📅 Hari: <b>{day}/7</b>\n🪙 Saldo Poin: <b>{bal:g}</b>\n\nHari 1-6 = 0.1 Poin\nHari 7 = 1 Poin.",
        "mycode":"📋 <b>MY CODE</b>\n\n", "no_code":"Belum ada code.",
        "top":"🔝 Top 10", "recommend":"⭐ Recommendation", "all":"🔑 All Code", "all_title":"🔑 <b>ALL CODE</b>",
        "top_title":"🔝 <b>TOP 10 CODE</b>", "rec_title":"⭐ <b>RECOMMENDATION</b>", "no_codes":"Belum ada code yang dibuat.",
        "click_title":"Klik <b>Judul</b> untuk mencari/membuka media yang terhubung dengan CODE tersebut.",
        "not_found":"❌ Code tidak ditemukan.", "all_code":"🔙 Semua Code", "like":"👍 Like", "hate":"👎 Hate", "fav":"⭐ Favorit",
        "buy_vip":"💎 <b>BUY VIP</b>\n\nPilih paket:", "group_channel":"👥 <b>GROUP & CHANNEL CODE</b>\n\nPilih tujuan yang ingin dibuka:",
        "group":"👥 Group Code","all_channel":"📚 Channel All Code","backup":"💾 Channel Backup","notice":"🔔 Channel Notifikasi",
        "send_points":"🪙 <b>KIRIM POIN</b>\n\nMasukkan <b>username Telegram penerima</b>.\nContoh: <code>@username</code>",
        "send_stars":"⭐ <b>KIRIM STAR</b>\n\nMasukkan <b>username Telegram penerima</b>.\nContoh: <code>@username</code>",
        "invalid_user":"❌ Username tidak valid. Masukkan username seperti <code>@username</code>.",
        "user_missing":"❌ Username belum ditemukan di bot. Pastikan penerima sudah /start terlebih dahulu.",
        "self":"❌ Kamu tidak bisa mengirim ke username sendiri.",
        "send_amount":"Masukkan jumlah {label} yang ingin dikirim:",
        "invalid_amount":"❌ Nominal tidak valid. Masukkan angka lebih dari 0.",
        "data_missing":"❌ Data pengguna tidak ditemukan.", "insufficient":"❌ <b>{label} tidak cukup.</b>\n\nSaldo kamu: <b>{balance:g} {label}</b>\nYang dibutuhkan: <b>{amount:g} {label}</b>",
        "sent":"✅ <b>{label} berhasil dikirim</b>\n\n👤 Penerima: <b>@{username}</b>\n💰 Jumlah: <b>{amount:g} {label}</b>\n💳 Sisa saldo: <b>{balance:g} {label}</b>",
        "received":"🎁 <b>Kamu menerima {label}</b>\n\n👤 Dari: <b>@{sender}</b>\n💰 Jumlah: <b>{amount:g} {label}</b>",
        "bot_links":"🔗 <b>LINK BOT</b>\n\nPilih tujuan yang kamu perlukan:", "points_balance":"🪙 <b>Poin kamu sekarang: {bal:g}</b>",
        "stars_balance":"⭐ <b>Star kamu sekarang: {bal:g}</b>", "buy_points":"🛒 Buy Poin","buy_stars":"🛒 Buy Star","send_points_btn":"📤 Kirim Poin","send_stars_btn":"📤 Kirim Star",
        "media_hint":"📎 <b>Media terdeteksi</b>\n\nTekan tombol di bawah untuk upload.","upfile":"📤 Up File",
        "start_first":"Klik /start dulu di bot. Setelah itu kamu bisa menekan GET FILE.","inactive":"Code tidak ditemukan atau sudah tidak aktif.",
        "detected":"CODE TERDETEKSI\n\nCode: <code>{code}</code>\nMedia: <b>{count}</b>\n\nPilih GET FILE untuk melanjutkan.",
        "sent_get":"GET FILE dikirim ke chat pribadi.","open_private":"Buka chat pribadi dengan bot lalu klik /start."
    },
    "en": {
        "join_creator":"👑 Join Creator","pay_creator":"💳 Pay Registration Rp200,000","back":"🔙 Back",
        "creator_title":"👑 <b>CREATOR PROGRAM</b>","creator_desc":"Become a creator and make Paid CODEs from your media.",
        "creator_req":"📋 <b>Requirements & refund scheme:</b>","period":"• Evaluation period: 1 month from registration.",
        "target":"• If you attract <b>{n} members</b>: registration refund/commission <b>{p}%</b>.",
        "target_last":"• If the target is not reached during the period, contact Admin to ask about requirements and the next period.",
        "note":"⚠️ <b>Note:</b> targets and refunds are subject to Admin verification.",
        "creator_contact":"• Contact the admin if you need help or verification.",
        "checkin_done":"You already checked in today.","checkin_reward":"+{x} Points","checkin":"🎁 <b>CHECK IN</b>\n\n📅 Day: <b>{day}/7</b>\n🪙 Point Balance: <b>{bal:g}</b>\n\nDays 1-6 = 0.1 Point\nDay 7 = 1 Point.",
        "mycode":"📋 <b>MY CODE</b>\n\n","no_code":"No code yet.","top":"🔝 Top 10","recommend":"⭐ Recommendation","all":"🔑 All Code",
        "all_title":"🔑 <b>ALL CODE</b>","top_title":"🔝 <b>TOP 10 CODE</b>","rec_title":"⭐ <b>RECOMMENDATION</b>","no_codes":"No codes have been created.",
        "click_title":"Click the <b>Title</b> to find/open media linked to this CODE.","not_found":"❌ Code not found.","all_code":"🔙 All Code","like":"👍 Like","hate":"👎 Hate","fav":"⭐ Favorite",
        "buy_vip":"💎 <b>BUY VIP</b>\n\nChoose a package:","group_channel":"👥 <b>GROUP & CHANNEL CODE</b>\n\nChoose a destination to open:",
        "group":"👥 Code Group","all_channel":"📚 All Code Channel","backup":"💾 Backup Channel","notice":"🔔 Notification Channel",
        "send_points":"🪙 <b>SEND POINTS</b>\n\nEnter the recipient's <b>Telegram username</b>.\nExample: <code>@username</code>","send_stars":"⭐ <b>SEND STAR</b>\n\nEnter the recipient's <b>Telegram username</b>.\nExample: <code>@username</code>",
        "invalid_user":"❌ Invalid username. Enter a username like <code>@username</code>.","user_missing":"❌ Username was not found. Make sure the recipient has started the bot with /start.","self":"❌ You cannot send to your own username.","send_amount":"Enter the amount of {label} to send:",
        "invalid_amount":"❌ Invalid amount. Enter a number greater than 0.","data_missing":"❌ User data not found.","insufficient":"❌ <b>Not enough {label}.</b>\n\nYour balance: <b>{balance:g} {label}</b>\nRequired: <b>{amount:g} {label}</b>",
        "sent":"✅ <b>{label} sent successfully</b>\n\n👤 Recipient: <b>@{username}</b>\n💰 Amount: <b>{amount:g} {label}</b>\n💳 Remaining balance: <b>{balance:g} {label}</b>",
        "received":"🎁 <b>You received {label}</b>\n\n👤 From: <b>@{sender}</b>\n💰 Amount: <b>{amount:g} {label}</b>",
        "bot_links":"🔗 <b>BOT LINKS</b>\n\nChoose the destination you need:","points_balance":"🪙 <b>Your current Points: {bal:g}</b>","stars_balance":"⭐ <b>Your current Stars: {bal:g}</b>",
        "buy_points":"🛒 Buy Points","buy_stars":"🛒 Buy Stars","send_points_btn":"📤 Send Points","send_stars_btn":"📤 Send Stars","media_hint":"📎 <b>Media detected</b>\n\nPress the button below to upload.","upfile":"📤 Up File",
        "start_first":"Click /start in the bot first. Then you can press GET FILE.","inactive":"Code not found or no longer active.","detected":"CODE DETECTED\n\nCode: <code>{code}</code>\nMedia: <b>{count}</b>\n\nChoose GET FILE to continue.","sent_get":"GET FILE was sent to your private chat.","open_private":"Open the bot's private chat and click /start."
    },
    "zh": {
        "join_creator":"👑 加入创作者","pay_creator":"💳 支付注册费 Rp200.000","back":"🔙 返回",
        "creator_title":"👑 <b>创作者计划</b>","creator_desc":"成为创作者，用你的媒体创建付费 CODE。",
        "creator_req":"📋 <b>要求与返还方案：</b>","period":"• 评估期：注册后 1 个月。",
        "target":"• 如果吸引 <b>{n} 名会员</b>：返还/注册佣金 <b>{p}%</b>。","target_last":"• 如果在期间内未达到目标，可以联系管理员咨询要求和下一阶段。",
        "note":"⚠️ <b>注意：</b>目标和返还需经过管理员审核。","creator_contact":"点击 <b>加入创作者</b> 联系管理员并进行注册。",
        "checkin_done":"今天已经签到。","checkin_reward":"+{x} 积分","checkin":"🎁 <b>签到</b>\n\n📅 第 <b>{day}/7</b> 天\n🪙 积分余额：<b>{bal:g}</b>\n\n第1-6天 = 0.1 积分\n第7天 = 1 积分。",
        "mycode":"📋 <b>我的 CODE</b>\n\n","no_code":"还没有 CODE。","top":"🔝 前10名","recommend":"⭐ 推荐","all":"🔑 全部 CODE",
        "all_title":"🔑 <b>全部 CODE</b>","top_title":"🔝 <b>热门前10 CODE</b>","rec_title":"⭐ <b>推荐</b>","no_codes":"还没有创建 CODE。",
        "click_title":"点击<b>标题</b>查找/打开与此 CODE 关联的媒体。","not_found":"❌ 未找到 CODE。","all_code":"🔙 全部 CODE","like":"👍 喜欢","hate":"👎 不喜欢","fav":"⭐ 收藏",
        "buy_vip":"💎 <b>购买 VIP</b>\n\n请选择套餐：","group_channel":"👥 <b>群组与频道 CODE</b>\n\n请选择要打开的目标：","group":"👥 CODE 群组","all_channel":"📚 全部 CODE 频道","backup":"💾 备份频道","notice":"🔔 通知频道",
        "send_points":"🪙 <b>发送积分</b>\n\n输入接收者的<b>Telegram 用户名</b>。\n示例：<code>@username</code>","send_stars":"⭐ <b>发送 Star</b>\n\n输入接收者的<b>Telegram 用户名</b>。\n示例：<code>@username</code>",
        "invalid_user":"❌ 用户名无效。请输入类似 <code>@username</code> 的用户名。","user_missing":"❌ 未找到该用户名。请确认接收者已经 /start。","self":"❌ 不能发送给自己的用户名。","send_amount":"请输入要发送的 {label} 数量：",
        "invalid_amount":"❌ 数量无效。请输入大于 0 的数字。","data_missing":"❌ 未找到用户数据。","insufficient":"❌ <b>{label} 不足。</b>\n\n你的余额：<b>{balance:g} {label}</b>\n需要：<b>{amount:g} {label}</b>",
        "sent":"✅ <b>{label} 发送成功</b>\n\n👤 接收者：<b>@{username}</b>\n💰 数量：<b>{amount:g} {label}</b>\n💳 剩余余额：<b>{balance:g} {label}</b>",
        "received":"🎁 <b>你收到 {label}</b>\n\n👤 来自：<b>@{sender}</b>\n💰 数量：<b>{amount:g} {label}</b>",
        "bot_links":"🔗 <b>机器人链接</b>\n\n请选择需要的目标：","points_balance":"🪙 <b>当前积分：{bal:g}</b>","stars_balance":"⭐ <b>当前 Star：{bal:g}</b>",
        "buy_points":"🛒 购买积分","buy_stars":"🛒 购买 Star","send_points_btn":"📤 发送积分","send_stars_btn":"📤 发送 Star","media_hint":"📎 <b>检测到媒体</b>\n\n点击下面按钮上传。","upfile":"📤 上传文件",
        "start_first":"请先在机器人中点击 /start，然后再点击 GET FILE。","inactive":"CODE 不存在或已停用。","detected":"检测到 CODE\n\nCode：<code>{code}</code>\n媒体：<b>{count}</b>\n\n选择 GET FILE 继续。","sent_get":"GET FILE 已发送到私聊。","open_private":"打开机器人私聊并点击 /start。"
    }
}
async def _t(uid, key, **kwargs):
    lang=await _lang(uid)
    return UI_TEXT.get(lang, UI_TEXT["id"]).get(key, UI_TEXT["id"].get(key, key)).format(**kwargs)

async def _buy_balance_kb(kind: str, uid: int = 0):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await _t(uid, 'buy_points' if kind=='points' else 'buy_stars'), callback_data='buy_points' if kind=='points' else 'buy_stars')]
    ])


def _code_link(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={code}"

def _safe_url(s: str) -> str:
    return html.escape(s, quote=True)

@router.callback_query(F.data=='creator_apply')
async def creator_apply(c):
    await loading(c)
    admin_url=f"tg://user?id={int(CREATOR_ADMIN_ID)}" if CREATOR_ADMIN_ID else ""
    text=(
        await _t(c.from_user.id,"creator_title")+"\n\n"+
        await _t(c.from_user.id,"creator_desc")+"\n\n"+
        "💰 <b>Rp200.000</b>\n\n"+
        await _t(c.from_user.id,"creator_req")+"\n"+
        await _t(c.from_user.id,"period")+"\n"+
        await _t(c.from_user.id,"target",n="200",p="20")+"\n"+
        await _t(c.from_user.id,"target",n="500",p="50")+"\n"+
        await _t(c.from_user.id,"target",n="1.000",p="100")+"\n"+
        await _t(c.from_user.id,"target_last")+"\n\n"+
        await _t(c.from_user.id,"note")+"\n\n"+
        await _t(c.from_user.id,"creator_contact")
    )
    kb=[]
    if admin_url:
        kb.append([InlineKeyboardButton(text=await _t(c.from_user.id,"join_creator"),url=admin_url)])
    kb.append([InlineKeyboardButton(text=await _t(c.from_user.id,"pay_creator"),callback_data="creator_buy")])
    kb.append([InlineKeyboardButton(text="🔙 Kembali",callback_data="menu_lainnya")])
    await c.message.edit_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data=='checkin')
async def ci(c):
    bal,day,ok=await checkin(c.from_user.id)
    await c.answer(await _t(c.from_user.id,'checkin_done') if not ok else await _t(c.from_user.id,'checkin_reward',x=1 if day==7 else 0.1))
    await c.message.edit_text(
        await _t(c.from_user.id,'checkin',day=day,bal=float(bal)),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=await _t(uid,'back'),callback_data='menu_lainnya')]])
    )

@router.callback_query(F.data=='my_code')
async def my(c):
    rows=await (await get_pool()).fetch(
        "SELECT code,title,media_count,views,likes,hates,favorites FROM files "
        "WHERE owner_id=$1 AND active=TRUE ORDER BY id DESC LIMIT 30", c.from_user.id
    )
    text=await _t(c.from_user.id,'mycode')
    kb=[]
    if rows:
        for r in rows:
            title=html.escape((r['title'] or 'Untitled')[:45])
            text += f"📝 <b>{title}</b>\n🔑 <code>{html.escape(r['code'])}</code> • {r['media_count']} media\n"
            text += f"👁 {r['views']} • 👍 {r['likes']} • 👎 {r['hates']} • ⭐ {r['favorites']}\n\n"
            kb.append([InlineKeyboardButton(text=f"📝 {title}", callback_data=f"browsecode:{r['code']}")])
    else:
        text+=await _t(c.from_user.id,'no_code')
    kb.append([InlineKeyboardButton(text=await _t(uid,'back'),callback_data='menu_lainnya')])
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

async def _code_nav(page,total,mode,uid=0):
    pages=max(1,(total+9)//10)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'{mode}page:{page-1}'))
    nav.append(InlineKeyboardButton(text=f'📄 {page+1}/{pages}',callback_data='noop'))
    if page<pages-1: nav.append(InlineKeyboardButton(text='➡️',callback_data=f'{mode}page:{page+1}'))
    rows=[nav]
    if mode=="all":
        rows.append([
            InlineKeyboardButton(text=await _t(uid,'top'),callback_data='top_codes'),
            InlineKeyboardButton(text=await _t(uid,'recommend'),callback_data='recommendation')
        ])
    elif mode=="top":
        rows.append([InlineKeyboardButton(text=await _t(uid,'recommend'),callback_data='recommendation'),
                     InlineKeyboardButton(text=await _t(uid,'all'),callback_data='code_all')])
    else:
        rows.append([InlineKeyboardButton(text=await _t(uid,'top'),callback_data='top_codes'),
                     InlineKeyboardButton(text=await _t(uid,'all'),callback_data='code_all')])
    rows.append([InlineKeyboardButton(text=await _t(uid,'back'),callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _render_code_list(c,page=0,mode="all"):
    rows,total=await _paged_codes(page,mode,10)
    heading={"all":await _t(c.from_user.id,"all_title"),"top":await _t(c.from_user.id,"top_title"),"recommend":await _t(c.from_user.id,"rec_title")}[mode]
    text=heading+"\n\n"
    if not rows:
        text+="Belum ada code yang dibuat."
    else:
        for i,r in enumerate(rows, page*10+1):
            text+=_code_text_row(r, f"{i}. " if mode!="all" else "")
        text+="Klik <b>Judul</b> untuk mencari/membuka media yang terhubung dengan CODE tersebut."
    await c.message.edit_text(text,parse_mode='HTML',reply_markup=await _code_nav(page,total,mode,c.from_user.id))

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
    if not f: return await c.answer(await _t(c.from_user.id,'not_found'),show_alert=True)
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
            [InlineKeyboardButton(text=await _t(c.from_user.id,'like'),callback_data=f'react:like:{f["code"]}'),
             InlineKeyboardButton(text=await _t(c.from_user.id,'hate'),callback_data=f'react:hate:{f["code"]}'),
             InlineKeyboardButton(text=await _t(c.from_user.id,'fav'),callback_data=f'react:favorite:{f["code"]}')],
            [InlineKeyboardButton(text=await _t(c.from_user.id,'all_code'),callback_data='code_all')]
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


def _help_pages(lang: str):
    text = HELP_TEXTS.get(lang, HELP_TEXTS["id"])
    paragraphs = [x.strip() for x in text.split("\n\n") if x.strip()]
    pages = []
    current = ""
    # Telegram message text limit is 4096 characters. Keep a safe margin
    # because HTML/entity handling and future edits can change the size.
    limit = 3400
    for paragraph in paragraphs:
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                pages.append(current)
            # A single section should also never exceed the limit.
            while len(paragraph) > limit:
                cut = paragraph.rfind("\n", 0, limit)
                if cut < 1000:
                    cut = limit
                pages.append(paragraph[:cut].strip())
                paragraph = paragraph[cut:].strip()
            current = paragraph
    if current:
        pages.append(current)
    return pages or [""]

async def _help_keyboard(lang: str, page: int, uid: int = 0):
    pages = _help_pages(lang)
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="‹ Prev", callback_data=f"help:page:{lang}:{page-1}"))
    if page < len(pages)-1:
        nav.append(InlineKeyboardButton(text="Next ›", callback_data=f"help:page:{lang}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(text='🇮🇩 Indonesia',callback_data='help:lang:id'),
        InlineKeyboardButton(text='🇬🇧 English',callback_data='help:lang:en'),
        InlineKeyboardButton(text='🇨🇳 中文',callback_data='help:lang:zh')
    ])
    rows.append([InlineKeyboardButton(text=f"Page {page+1}/{len(pages)}", callback_data='help:noop')])
    rows.append([InlineKeyboardButton(text=await _t(uid,'back'),callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data=='help')
async def help_(c):
    await loading(c)
    await c.message.edit_text(
        _help_pages("id")[0],
        parse_mode='HTML',
        reply_markup=await _help_keyboard("id", 0, c.from_user.id)
    )

@router.callback_query(F.data.startswith('help:lang:'))
async def help_lang(c):
    lang=c.data.rsplit(':',1)[1]
    if lang not in HELP_TEXTS: lang="id"
    await loading(c)
    await c.message.edit_text(
        _help_pages(lang)[0],
        parse_mode='HTML',
        reply_markup=await _help_keyboard(lang, 0, c.from_user.id)
    )

@router.callback_query(F.data.startswith('help:page:'))
async def help_page(c):
    parts=c.data.split(':')
    lang=parts[2] if len(parts) > 2 else 'id'
    try:
        page=int(parts[3])
    except (ValueError, IndexError):
        page=0
    if lang not in HELP_TEXTS:
        lang='id'
    pages=_help_pages(lang)
    page=max(0, min(page, len(pages)-1))
    await loading(c)
    await c.message.edit_text(
        pages[page],
        parse_mode='HTML',
        reply_markup=await _help_keyboard(lang, page, c.from_user.id)
    )

@router.callback_query(F.data=='help:noop')
async def help_noop(c):
    await c.answer()

@router.callback_query(F.data=='buy_vip')
async def vip(c):
    rows=await (await get_pool()).fetch("SELECT code,name,price,duration_days FROM vip_packages WHERE active ORDER BY price")
    kb=[[InlineKeyboardButton(text=f'💎 {r["name"]} • Rp{int(r["price"]):,}'.replace(',','.'),callback_data=f'vip:{r["code"]}')] for r in rows]
    kb.append([InlineKeyboardButton(text=await _t(c.from_user.id,'back'),callback_data='home')])
    await loading(c); await c.message.edit_text(await _t(c.from_user.id,'buy_vip'),parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def quick_links(uid: int = 0):
    # Group Code opens a dedicated link menu so users can choose the
    # group/all-code/backup/notification destination.
    rows=[]
    rows.append([InlineKeyboardButton(text=await _t(uid,'group'),callback_data='open_group_info')])
    return rows

@router.callback_query(F.data=='open_group_info')
async def open_group_info(c):
    await loading(c)
    uid = c.from_user.id
    rows = [
        [InlineKeyboardButton(text=await _t(uid, 'group'), url=DIRECT_GROUP_CODE_URL)],
        [InlineKeyboardButton(text=await _t(uid, 'all_channel'), url=DIRECT_ALL_CODE_URL)],
        [InlineKeyboardButton(text=await _t(uid, 'backup'), url=DIRECT_BACKUP_URL)],
        [InlineKeyboardButton(text=await _t(uid, 'notice'), url=DIRECT_NOTICE_URL)],
        [InlineKeyboardButton(text=await _t(uid, 'back'), callback_data='menu_lainnya')],
    ]
    await c.message.edit_text(
        await _t(uid, 'group_channel'),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )

@router.callback_query(F.data=='open_notice_info')
async def open_notice_info(c):
    await open_group_info(c)


@router.callback_query(F.data == 'send_points')
async def send_points_start(c, state: FSMContext):
    await state.clear()
    await state.set_state(TransferState.username)
    await c.message.answer(
        "🪙 <b>KIRIM POIN</b>\n\n"
        "Masukkan <b>username Telegram penerima</b>.\n"
        "Contoh: <code>@username</code>",
        parse_mode='HTML'
    )
    await c.answer()

@router.callback_query(F.data == 'send_stars')
async def send_stars_start(c, state: FSMContext):
    await state.clear()
    await state.set_state(TransferState.username)
    await state.update_data(kind='stars')
    await c.message.answer(
        "⭐ <b>KIRIM STAR</b>\n\n"
        "Masukkan <b>username Telegram penerima</b>.\n"
        "Contoh: <code>@username</code>",
        parse_mode='HTML'
    )
    await c.answer()

@router.message(TransferState.username, F.chat.type == 'private', F.text)
async def transfer_username(m, state: FSMContext):
    username=(m.text or '').strip().lstrip('@').strip()
    if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', username):
        await m.answer(await _t(m.from_user.id,"invalid_user"), parse_mode='HTML')
        return
    p=await get_pool()
    r=await p.fetchrow("SELECT user_id,username FROM users WHERE lower(username)=lower($1) LIMIT 1", username)
    if not r:
        await m.answer(await _t(m.from_user.id,"user_missing"))
        return
    if int(r['user_id']) == int(m.from_user.id):
        await m.answer(await _t(m.from_user.id,"self"))
        return
    data=await state.get_data()
    kind=data.get('kind','points')
    await state.update_data(receiver_id=int(r['user_id']), receiver_username=username, kind=kind)
    await state.set_state(TransferState.amount)
    label='Poin' if kind=='points' else 'Star'
    await m.answer(
        f"🪙 <b>KIRIM {label.upper()}</b>\n\n"
        f"Penerima: <b>@{html.escape(username)}</b>\n"
        f"Masukkan jumlah {label.lower()} yang ingin dikirim:",
        parse_mode='HTML'
    )

@router.message(TransferState.amount, F.chat.type == 'private', F.text)
async def transfer_amount(m, state: FSMContext):
    data=await state.get_data()
    kind=data.get('kind','points')
    try:
        amount=Decimal((m.text or '').replace(',','.').strip())
    except Exception:
        amount=Decimal('0')
    if amount <= 0 or amount != amount.quantize(Decimal('0.01')):
        await m.answer(await _t(m.from_user.id,"invalid_amount"))
        return
    receiver_id=int(data['receiver_id'])
    sender_id=int(m.from_user.id)
    col='points' if kind=='points' else 'stars'
    table='point_transfers' if kind=='points' else 'star_transfers'
    label='Poin' if kind=='points' else 'Star'
    p=await get_pool()
    async with p.acquire() as conn:
        async with conn.transaction():
            sender=await conn.fetchrow(f"SELECT {col},username FROM users WHERE user_id=$1 FOR UPDATE",sender_id)
            receiver=await conn.fetchrow("SELECT user_id,username FROM users WHERE user_id=$1 FOR UPDATE",receiver_id)
            if not sender or not receiver:
                await state.clear()
                await m.answer(await _t(m.from_user.id,"data_missing"))
                return
            balance=Decimal(str(sender[col] or 0))
            if balance < amount:
                await state.clear()
                await m.answer(
                    f"❌ <b>Poin tidak cukup.</b>\n\n"
                    f"Saldo kamu: <b>{balance:g} {label}</b>\n"
                    f"Yang dibutuhkan: <b>{amount:g} {label}</b>",
                    parse_mode='HTML',
                    reply_markup=await _buy_balance_kb(kind,m.from_user.id)
                )
                return
            await conn.execute(f"UPDATE users SET {col}={col}-$1 WHERE user_id=$2",amount,sender_id)
            await conn.execute(f"UPDATE users SET {col}={col}+$1 WHERE user_id=$2",amount,receiver_id)
            await conn.execute(f"INSERT INTO {table}(sender_id,receiver_id,amount) VALUES($1,$2,$3)",sender_id,receiver_id,amount)
            new_balance=balance-amount
    await state.clear()
    username=data.get('receiver_username','')
    await m.answer(
        f"✅ <b>{label} berhasil dikirim</b>\n\n"
        f"👤 Penerima: <b>@{html.escape(username)}</b>\n"
        f"💰 Jumlah: <b>{amount:g} {label}</b>\n"
        f"💳 Sisa saldo: <b>{new_balance:g} {label}</b>",
        parse_mode='HTML'
    )
    try:
        await m.bot.send_message(
            receiver_id,
            f"🎁 <b>Kamu menerima {label}</b>\n\n"
            f"👤 Dari: <b>@{html.escape(m.from_user.username or str(sender_id))}</b>\n"
            f"💰 Jumlah: <b>{amount:g} {label}</b>",
            parse_mode='HTML'
        )
    except Exception:
        pass

@router.message(F.chat.type=='private', F.text, ~F.text.startswith('/'))
async def keyword_help(m:Message):
    text=(m.text or '').strip().lower()
    if text in {'group','vip','video'}:
        rows=await quick_links(m.from_user.id)
        await m.answer(await _t(m.from_user.id,"bot_links"),parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text='🏠 Menu',callback_data='home')]]))
        return
    if text in {'poin','point','points'}:
        p=await get_pool(); bal=await p.fetchval('SELECT points FROM users WHERE user_id=$1',m.from_user.id) or 0
        await m.answer(await _t(m.from_user.id,'points_balance',bal=float(bal)),parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                           [InlineKeyboardButton(text=await _t(m.from_user.id,'buy_points'),callback_data='buy_points')],
                           [InlineKeyboardButton(text=await _t(m.from_user.id,'send_points_btn'),callback_data='send_points')]
                       ]))
        return
    if text in {'star','stars'}:
        p=await get_pool(); bal=await p.fetchval('SELECT stars FROM users WHERE user_id=$1',m.from_user.id) or 0
        await m.answer(await _t(m.from_user.id,'stars_balance',bal=float(bal)),parse_mode='HTML',
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                           [InlineKeyboardButton(text=await _t(m.from_user.id,'buy_stars'),callback_data='buy_stars')],
                           [InlineKeyboardButton(text=await _t(m.from_user.id,'send_stars_btn'),callback_data='send_stars')]
                       ]))

async def media_hint(m:Message):
    await m.answer(await _t(m.from_user.id,'media_hint'),parse_mode='HTML',
                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=await _t(m.from_user.id,'upfile'),callback_data='upfile')]]))

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
        await c.answer(await _t(c.from_user.id,"start_first"), show_alert=True)
        return

    f=await p.fetchrow(
        "SELECT code,title,media_count,price_idr,active FROM files "
        "WHERE lower(code)=lower($1) AND active=TRUE",code
    )
    if not f:
        await c.answer(await _t(c.from_user.id,"inactive"), show_alert=True)
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
        await c.answer(await _t(c.from_user.id,"sent_get"))
    except Exception:
        await c.answer(await _t(c.from_user.id,"open_private"), show_alert=True)
