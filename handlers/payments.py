from aiogram import Router,F
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,BufferedInputFile
from config import POINT_PACKAGES,STAR_PACKAGES
from keyboards.menu import provider_kb
from utils.payments import create_purchase,qr_bytes,enabled
router=Router()

def fmt(n):return f"Rp{int(n):,}".replace(',','.')
@router.callback_query(F.data=='buy_points')
async def buy_points(call):
 rows=[[InlineKeyboardButton(text=f"🪙 {q} Poin • {fmt(v)}",callback_data=f"choosepay:points:{q}:{v}")] for q,v in POINT_PACKAGES.items()]; rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]); await call.answer(); await call.message.edit_text('🪙 <b>BUY POIN</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
@router.callback_query(F.data=='buy_stars')
async def buy_stars(call):
 rows=[[InlineKeyboardButton(text=f"⭐ {q} Star • {fmt(v)}",callback_data=f"choosepay:stars:{q}:{v}")] for q,v in STAR_PACKAGES.items()]; rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')]); await call.answer(); await call.message.edit_text('⭐ <b>BUY STAR</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
@router.callback_query(F.data.startswith('choosepay:'))
async def choose(call):
    _,typ,qty,amount=call.data.split(':')
    await call.answer()
    rows=[]
    payload=f"{typ}:{qty}:{amount}"
    if await enabled("bayargg"):
        rows.append([InlineKeyboardButton(text="⚡ BayarGG",callback_data=f"provider:{payload}:bayargg")])
    if await enabled("cashi"):
        rows.append([InlineKeyboardButton(text="💳 Cashi",callback_data=f"provider:{payload}:cashi")])
    rows.append([InlineKeyboardButton(text="🔙 Kembali",callback_data="home")])
    if len(rows)==1:
        return await call.message.edit_text(
            "⚠️ Semua pembayaran sedang ditutup oleh admin.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
    await call.message.edit_text(
        f"💳 <b>PILIH PEMBAYARAN</b>\n\n{'🪙' if typ=='points' else '⭐'} Paket: <b>{qty} {'Poin' if typ=='points' else 'Star'}</b>\n💵 Harga: <b>{fmt(amount)}</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )

@router.callback_query(F.data.startswith('provider:'))
async def provider(call):
 _,payload,provider=call.data.split(':',2); typ,qty,amount=payload.split(':'); qty=int(qty); amount=int(amount)
 r,status=await create_purchase(call.from_user.id,typ,qty,amount,provider,call.from_user.full_name)
 if not r:return await call.answer('❌ Pembayaran sedang ditutup atau provider gagal.',show_alert=True)
 data=qr_bytes(r['qr_string']); await call.answer('Invoice dibuat.')
 text=f"💳 <b>PEMBAYARAN</b>\n\n📦 {qty} {'Poin' if typ=='points' else 'Star'}\n💵 {fmt(amount)}\n🏦 {provider.upper()}\n🧾 <code>{r['invoice_id']}</code>\n\nBayar sesuai nominal. Saldo masuk otomatis setelah pembayaran terverifikasi."
 if data: await call.message.answer_photo(BufferedInputFile(data,filename='payment.png'),caption=text,parse_mode='HTML')
 else: await call.message.answer(text,parse_mode='HTML')
