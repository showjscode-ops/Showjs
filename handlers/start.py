
from aiogram import Router,F
from aiogram.filters import CommandStart
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from database import get_pool
from keyboards.menu import home_kb,other_menu_kb
from utils.economy import ensure_user,is_creator,is_vip
from middlewares.subscription import subscription_prompt
from utils.callback_loading import loading
router=Router()
async def dashboard_text(uid):
 p=await get_pool(); r=await p.fetchrow("SELECT points,stars,balance,is_creator,creator_status,vip,vip_until FROM users WHERE user_id=$1",uid)
 creator=bool(r and r['is_creator'] and r['creator_status']=='approved')
 vip=bool(r and r['vip'] and (r['vip_until'] is None or r['vip_until']>__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
 status='CREATOR' if creator else ('VIP' if vip else 'FREE')
 return f"👤 <b>Dashboard</b>\n\n🆔 ID: <code>{uid}</code>\n🟢 Status: <b>{status}</b>\n💰 Saldo: <b>Rp{int(r['balance'] or 0):,}</b>\n🪙 Poin: <b>{float(r['points'] or 0):g}</b>\n⭐ Star: <b>{float(r['stars'] or 0):g}</b>\n\n💡 Belum paham cara menggunakan bot? Klik <b>Help</b> untuk melihat panduan lengkap.".replace(',','.'),creator

@router.message(CommandStart())
async def start(m):
 await ensure_user(m.from_user.id,m.from_user.username,m.from_user.full_name)
 # Telegram deep-link: https://t.me/<bot>?start=<CODE>
 parts=(m.text or '').split(maxsplit=1)
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
 return await message.answer(POINTS_HELP_TEXT,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Help",callback_data="help")]]))
