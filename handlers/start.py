from aiogram import Router,F
from aiogram.filters import CommandStart
from aiogram.types import Message,CallbackQuery
from database import get_pool
from keyboards.menu import home_kb,other_menu_kb
from utils.economy import ensure_user,is_creator
from middlewares.subscription import subscription_prompt
from utils.callback_loading import loading
router=Router()
async def dashboard_text(uid):
 p=await get_pool(); r=await p.fetchrow("SELECT points,stars,is_creator,creator_status,vip,vip_until FROM users WHERE user_id=$1",uid); creator=bool(r and r['is_creator'] and r['creator_status']=='approved'); status='CREATOR' if creator else ('VIP' if r and r['vip'] else 'FREE');
 return f"👤 <b>Dashboard</b>\n\n🆔 ID: <code>{uid}</code>\n🟢 Status: <b>{status}</b>\n🪙 Poin: <b>{float(r['points'] or 0):g}</b>\n⭐ Star: <b>{float(r['stars'] or 0):g}</b>",creator
@router.message(CommandStart())
async def start(m): await ensure_user(m.from_user.id,m.from_user.username,m.from_user.full_name); t,c=await dashboard_text(m.from_user.id); await m.answer(t,parse_mode='HTML',reply_markup=home_kb())
@router.callback_query(F.data=='home')
async def home(c:CallbackQuery): await loading(c); await ensure_user(c.from_user.id,c.from_user.username,c.from_user.full_name); t,_=await dashboard_text(c.from_user.id); await c.message.edit_text(t,parse_mode='HTML',reply_markup=home_kb())
@router.callback_query(F.data=='menu_lainnya')
async def more(c): await loading(c); await c.message.edit_text('📂 <b>MENU LAINNYA</b>',parse_mode='HTML',reply_markup=other_menu_kb(await is_creator(c.from_user.id)))

@router.callback_query(F.data=='verify_join')
async def verify_join(c:CallbackQuery):
    await loading(c)
    if not await subscription_prompt(c.bot,c.from_user.id,c.from_user.id):
        return
    await ensure_user(c.from_user.id,c.from_user.username,c.from_user.full_name)
    t,_=await dashboard_text(c.from_user.id)
    try:
        await c.message.edit_text(t,parse_mode='HTML',reply_markup=home_kb())
    except Exception:
        await c.message.answer(t,parse_mode='HTML',reply_markup=home_kb())
