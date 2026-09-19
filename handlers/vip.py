from aiogram import Router,F
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,BufferedInputFile
from database import get_pool
from utils.payments import create_purchase,qr_bytes
from utils.callback_loading import loading
router=Router()
@router.callback_query(F.data.startswith('vip:'))
async def choose(c):
 code=c.data.split(':',1)[1]; p=await get_pool(); r=await p.fetchrow("SELECT * FROM vip_packages WHERE code=$1 AND active",code)
 if not r:return await c.answer('Paket tidak tersedia.',show_alert=True)
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⚡ BayarGG',callback_data=f'vip_provider:{code}:bayargg')],[InlineKeyboardButton(text='💳 Cashi',callback_data=f'vip_provider:{code}:cashi')],[InlineKeyboardButton(text='🔙 Kembali',callback_data='buy_vip')]])
 await loading(c); await c.message.edit_text(f'💎 {r["name"]}\n💵 Rp{int(r["price"]):,}'.replace(',','.'),reply_markup=kb)
@router.callback_query(F.data.startswith('vip_provider:'))
async def pay(c):
 _,code,provider=c.data.split(':'); p=await get_pool(); r=await p.fetchrow("SELECT * FROM vip_packages WHERE code=$1 AND active",code); result,status=await create_purchase(c.from_user.id,'vip',r['duration_days'],r['price'],provider,c.from_user.full_name)
 if not result:return await c.answer('❌ Pembayaran ditutup atau gagal.',show_alert=True)
 data=qr_bytes(result['qr_string']); await loading(c)
 text=f'💎 <b>{r["name"]}</b>\n💵 Rp{int(r["price"]):,}\n🏦 {provider.upper()}\n🧾 <code>{result["invoice_id"]}</code>\n\nPembayaran otomatis diverifikasi.'.replace(',','.')
 if data: await c.message.answer_photo(BufferedInputFile(data,filename='vip.png'),caption=text,parse_mode='HTML')
 else: await c.message.answer(text,parse_mode='HTML')
