
from aiogram import Router,F
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,BufferedInputFile
from database import get_pool
from utils.payments import create_purchase,qr_bytes,enabled
from utils.callback_loading import loading
router=Router()
@router.callback_query(F.data.startswith('buy_vip'))
async def listvip(c):
 rows=await (await get_pool()).fetch("SELECT code,name,price,duration_days FROM vip_packages WHERE active ORDER BY price")
 kb=[[InlineKeyboardButton(text=f'💎 {r["name"]} • Rp{int(r["price"]):,}'.replace(',','.'),callback_data=f'vip:{r["code"]}')] for r in rows]
 kb.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
 await c.message.edit_text('💎 <b>BUY VIP</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith('vip:'))
async def choose(c):
 code=c.data.split(':',1)[1]; r=await (await get_pool()).fetchrow("SELECT * FROM vip_packages WHERE code=$1 AND active",code)
 if not r:return await c.answer('Paket tidak tersedia.',show_alert=True)
 rows=[]
 if await enabled('bayargg'):rows.append([InlineKeyboardButton(text='⚡ BayarGG',callback_data=f'vip_provider:{code}:bayargg')])
 if await enabled('cashi'):rows.append([InlineKeyboardButton(text='💳 Cashi',callback_data=f'vip_provider:{code}:cashi')])
 if await enabled('manual'):rows.append([InlineKeyboardButton(text='🧾 QR Manual',callback_data=f'vip_manual:{code}')])
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='buy_vip')])
 await c.message.edit_text(f'💎 {r["name"]}\n💵 Rp{int(r["price"]):,}'.replace(',','.'),reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('vip_provider:'))
async def pay(c):
 _,code,provider=c.data.split(':'); r=await (await get_pool()).fetchrow("SELECT * FROM vip_packages WHERE code=$1 AND active",code)
 result,status=await create_purchase(c.from_user.id,'vip',r['duration_days'],r['price'],provider,c.from_user.full_name)
 if not result:return await c.answer('❌ Pembayaran ditutup atau gagal.',show_alert=True)
 data=qr_bytes(result.get('qr_string')); await c.answer()
 text=f'💎 <b>{r["name"]}</b>\n💵 Rp{int(r["price"]):,}\n🏦 {provider.upper()}\n🧾 <code>{result["invoice_id"]}</code>\n\nSetelah membayar, tekan Cek Pembayaran.'.replace(',','.')
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'paycheck:{result["invoice_id"]}')],[InlineKeyboardButton(text='❌ Batal',callback_data=f'paycancel:{result["invoice_id"]}')]])
 if data: await c.message.answer_photo(BufferedInputFile(data,filename='vip.png'),caption=text,parse_mode='HTML',reply_markup=kb)
 else: await c.message.answer(text,parse_mode='HTML',reply_markup=kb)

@router.callback_query(F.data.startswith('vip_manual:'))
async def vip_manual(c,state):
 from handlers.payments import ManualProofState
 code=c.data.split(':',1)[1]; r=await (await get_pool()).fetchrow("SELECT * FROM vip_packages WHERE code=$1 AND active",code)
 qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
 if not qr:return await c.answer('❌ QR manual belum dipasang.',show_alert=True)
 await state.set_state(ManualProofState.proof); await state.update_data(kind='vip',quantity=int(r['duration_days']),amount=int(r['price']),target_code=None)
 await c.message.answer_photo(qr,caption=f'🧾 <b>QR MANUAL VIP</b>\n\n{r["name"]}\n💰 Rp{int(r["price"]):,}\n\nKirim screenshot bukti pembayaran.'.replace(',','.'),parse_mode='HTML')
