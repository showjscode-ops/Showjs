
from aiogram import Router,F
from aiogram.filters import CommandStart
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from database import get_pool
from keyboards.menu import home_kb,other_menu_kb
from utils.economy import ensure_user,is_creator,is_vip
from middlewares.subscription import subscription_prompt
from utils.callback_loading import loading
from utils.i18n import get_lang,set_lang,SUPPORTED,LANG_KB
router=Router()

def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇮🇩 Indonesia", callback_data="lang:id")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang:zh")],
    ])

async def language_prompt(m):
    await m.answer(
        "🌐 <b>Pilih Bahasa / Choose Language / 选择语言</b>\n\n"
        "Pilih bahasa yang akan digunakan bot:",
        parse_mode="HTML", reply_markup=language_kb()
    )

async def dashboard_text(uid):
 p=await get_pool(); r=await p.fetchrow("SELECT points,stars,balance,is_creator,creator_status,vip,vip_until FROM users WHERE user_id=$1",uid)
 creator=bool(r and r['is_creator'] and r['creator_status']=='approved')
 vip=bool(r and r['vip'] and (r['vip_until'] is None or r['vip_until']>__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
 status='CREATOR' if creator else ('VIP' if vip else 'FREE')
 return f"👤 <b>Dashboard</b>\n\n🆔 ID: <code>{uid}</code>\n🟢 Status: <b>{status}</b>\n💰 Saldo: <b>Rp{int(r['balance'] or 0):,}</b>\n🪙 Poin: <b>{float(r['points'] or 0):g}</b>\n⭐ Star: <b>{float(r['stars'] or 0):g}</b>\n\n💡 Belum paham cara menggunakan bot? Klik <b>Help</b> untuk melihat panduan lengkap.".replace(',','.'),creator

@router.message(F.chat.type == 'private', CommandStart())
async def start(m):
 await ensure_user(m.from_user.id,m.from_user.username,m.from_user.full_name)
 await (await get_pool()).execute("UPDATE users SET bot_started_at=NOW() WHERE user_id=$1",m.from_user.id)
 current_lang=await get_lang(m.from_user.id)
 parts=(m.text or '').split(maxsplit=1)
 if not current_lang:
  pending=parts[1].strip() if len(parts)==2 and parts[1].strip() else None
  await (await get_pool()).execute("UPDATE users SET pending_start_code=$1 WHERE user_id=$2",pending,m.from_user.id)
  return await language_prompt(m)
 # Telegram deep-link: https://t.me/<bot>?start=<CODE>
 if len(parts)==2 and parts[1].strip():
  code=parts[1].strip()
  p=await get_pool()
  f=await p.fetchrow("SELECT code,title,media_count,views,likes,hates,favorites,price_idr FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)
  if f:
   import html as _html
   price=int(f['price_idr'] or 0)
   paid=(f"💰 Harga: <b>Rp{price:,}</b>".replace(',','.')) if price else "🆓 <b>FREE CODE</b>"
   await m.answer(
    f"📝 <b>{_html.escape(f['title'] or 'Untitled')}</b>\n\n"
    f"🔑 <code>{_html.escape(f['code'])}</code>\n"
    f"📦 Media: <b>{f['media_count']}</b>\n{paid}\n\n"
    f"👁 View: <b>{f['views']}</b> • 👍 <b>{f['likes']}</b> • 👎 <b>{f['hates']}</b> • ⭐ <b>{f['favorites']}</b>",
    parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📥 Buka Code',callback_data=f'getcode:{f["code"]}')]]))
   return
 t,_=await dashboard_text(m.from_user.id); await send_points_help(m); await m.answer(t,parse_mode='HTML',reply_markup=home_kb())


@router.callback_query(F.data.startswith("lang:"))
async def choose_language(c):
    lang=c.data.split(":",1)[1]
    if lang not in SUPPORTED:
        return await c.answer("Language unavailable.", show_alert=True)
    await set_lang(c.from_user.id,lang)
    try:
        import bot as _botmod
        _botmod._LANG_CACHE[c.from_user.id] = lang
    except Exception:
        pass
    p=await get_pool()
    pending=await p.fetchval("SELECT pending_start_code FROM users WHERE user_id=$1",c.from_user.id)
    await p.execute("UPDATE users SET pending_start_code=NULL WHERE user_id=$1",c.from_user.id)
    await c.answer()
    if pending:
        from handlers.getfile import show
        return await show(c.message,pending)
    t,_=await dashboard_text(c.from_user.id)
    await c.message.edit_text(t,parse_mode="HTML",reply_markup=home_kb())

@router.callback_query(F.data=="change_language")
async def change_language(c):
    await c.answer()
    await c.message.edit_text(
        "🌐 <b>Pilih Bahasa / Choose Language / 选择语言</b>\n\nPilih bahasa yang akan digunakan bot:",
        parse_mode="HTML", reply_markup=language_kb()
    )

@router.callback_query(F.data=='home')
async def home(c):
 await loading(c); await ensure_user(c.from_user.id,c.from_user.username,c.from_user.full_name); t,_=await dashboard_text(c.from_user.id)
 await c.message.edit_text(t,parse_mode='HTML',reply_markup=home_kb())

@router.callback_query(F.data=='menu_lainnya')
async def more(c):
 await loading(c); await c.message.edit_text('📂 <b>MENU LAINNYA</b>',parse_mode='HTML',reply_markup=other_menu_kb(await is_creator(c.from_user.id)))

@router.callback_query(F.data=='verify_join')
async def verify_join(c):
 await loading(c)
 if not await subscription_prompt(c.bot,c.from_user.id,c.from_user.id): return
 await ensure_user(c.from_user.id,c.from_user.username,c.from_user.full_name)
 t,_=await dashboard_text(c.from_user.id)
 try: await c.message.edit_text(t,parse_mode='HTML',reply_markup=home_kb())
 except: await c.message.answer(t,parse_mode='HTML',reply_markup=home_kb())

POINTS_HELP_TEXT=("💡 <b>Info Dashboard</b>\n\n"
"• 💰 Saldo untuk paid code dan deposit\n"
"• 🪙 Poin untuk membuka FREE media\n"
"• ⭐ Star untuk membuka media permanen sesuai aturan Star\n"
"• 💎 VIP dapat membuka semua media tanpa biaya\n"
"• ⏳ VIP dapat membuka code yang sama setiap 30 menit.")

@router.callback_query(F.data=="points_help_ok")
async def points_help_ok(c):
 try: await c.message.delete()
 except: pass
 await c.answer()

async def send_points_help(message):
 return await message.answer(POINTS_HELP_TEXT,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Help",callback_data="help")],[InlineKeyboardButton(text="✅ Done",callback_data="points_help_ok")]]))
