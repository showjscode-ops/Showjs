from aiogram import Router,F
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from database import get_pool
from utils.callback_loading import loading
router=Router()
@router.callback_query(F.data=='creator_dashboard')
async def creator(c):
 p=await get_pool(); r=await p.fetchrow("SELECT earnings,total_sales FROM users WHERE user_id=$1 AND is_creator AND creator_status='approved'",c.from_user.id)
 if not r:return await c.answer('Hanya Creator.',show_alert=True)
 today=await p.fetchval("SELECT COALESCE(SUM(creator_income_idr),0) FROM unlock_transactions WHERE creator_id=$1 AND created_at::date=CURRENT_DATE",c.from_user.id) or 0
 month=await p.fetchval("SELECT COALESCE(SUM(creator_income_idr),0) FROM unlock_transactions WHERE creator_id=$1 AND date_trunc('month',created_at)=date_trunc('month',NOW())",c.from_user.id) or 0
 opened=await p.fetchval("SELECT COUNT(*) FROM unlock_transactions WHERE creator_id=$1",c.from_user.id) or 0
 text=f"👑 <b>Creator</b>\n\n💰 Saldo Pendapatan\nRp {int(r['earnings'] or 0):,}\n\n💵 Pendapatan Hari Ini\nRp {int(today):,}\n\n📅 Pendapatan Bulan Ini\nRp {int(month):,}\n\n📦 Total Penjualan\n{int(r['total_sales'] or 0)}\n\n👁 Total Dibuka\n{int(opened)}".replace(',','.')
 await loading(c); await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Kembali',callback_data='menu_lainnya')]]))
