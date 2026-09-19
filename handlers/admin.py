from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import OWNER_ID,ADMIN_IDS,TRIAL_POINTS,TRIAL_STARS
from utils.callback_loading import loading
router=Router()
class CreatorState(StatesGroup): user_id=State()
def admin(uid):return uid==OWNER_ID or uid in ADMIN_IDS
async def val(key):return str(await (await get_pool()).fetchval('SELECT value FROM settings WHERE key=$1',key) or 'off')
async def panel_msg():
 return InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text='⚡ BayarGG ON/OFF',callback_data='adm:bayargg'),InlineKeyboardButton(text='💳 Cashi ON/OFF',callback_data='adm:cashi')],
  [InlineKeyboardButton(text='🧪 Trial ON/OFF',callback_data='adm:trial'),InlineKeyboardButton(text='🧪 Trial Owner',callback_data='adm:trial_owner')],
  [InlineKeyboardButton(text='👑 Grant Creator',callback_data='adm:creator')],
  [InlineKeyboardButton(text='🔄 Refresh',callback_data='adm:panel')]])
async def panel_text():return f"👑 <b>ADMIN PANEL</b>\n\n⚡ BayarGG: <b>{(await val('payment_bayargg_enabled')).upper()}</b>\n💳 Cashi: <b>{(await val('payment_cashi_enabled')).upper()}</b>\n🧪 Trial owner: <b>{(await val('trial_enabled')).upper()}</b>\n\nPanel hanya mengatur kontrol admin; aturan ekonomi user tetap sesuai konfigurasi bot."
@router.message(Command('panel'))
async def panel(m):
 if not admin(m.from_user.id):return
 await m.answer(await panel_text(),parse_mode='HTML',reply_markup=await panel_msg())
@router.callback_query(F.data=='adm:panel')
async def refresh(c):
 if not admin(c.from_user.id):return await c.answer('No access',show_alert=True)
 await loading(c); await c.message.edit_text(await panel_text(),parse_mode='HTML',reply_markup=await panel_msg())
@router.callback_query(F.data.startswith('adm:'))
async def toggle(c,state:FSMContext):
 if not admin(c.from_user.id):return await c.answer('No access',show_alert=True)
 key={'bayargg':'payment_bayargg_enabled','cashi':'payment_cashi_enabled','trial':'trial_enabled'}.get(c.data.split(':')[1])
 if key:
  old=await val(key); new='off' if old=='on' else 'on'; await (await get_pool()).execute('UPDATE settings SET value=$1 WHERE key=$2',new,key); await c.answer('Updated'); await c.message.edit_text(await panel_text(),parse_mode='HTML',reply_markup=await panel_msg()); return
 if c.data=='adm:creator':
  await loading(c); await state.set_state(CreatorState.user_id); await c.message.answer('Kirim Telegram ID user yang akan dijadikan Creator.'); return
 if c.data=='adm:trial_owner':
  if c.from_user.id!=OWNER_ID: return await c.answer('Khusus owner.',show_alert=True)
  if (await val('trial_enabled'))!='on': return await c.answer('Trial sedang OFF.',show_alert=True)
  await (await get_pool()).execute('UPDATE users SET points=points+$1,stars=stars+$2 WHERE user_id=$3',TRIAL_POINTS,TRIAL_STARS,OWNER_ID)
  await (await get_pool()).execute('INSERT INTO trial_logs(owner_id,points_added,stars_added) VALUES($1,$2,$3)',OWNER_ID,TRIAL_POINTS,TRIAL_STARS)
  return await c.answer(f'+{TRIAL_POINTS:g} Poin / +{TRIAL_STARS:g} Star',show_alert=True)

@router.message(CreatorState.user_id)
async def grant_creator(m:Message,state:FSMContext):
 if not admin(m.from_user.id): return
 try: uid=int((m.text or '').strip())
 except: return await m.answer('❌ ID tidak valid.')
 p=await get_pool(); r=await p.fetchrow("UPDATE users SET is_creator=TRUE,creator_status='approved' WHERE user_id=$1 RETURNING user_id",uid)
 await state.clear(); await m.answer('✅ Creator diaktifkan.' if r else '❌ User belum ada di database.')
