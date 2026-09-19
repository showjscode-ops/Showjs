from aiogram import Router,F
from aiogram.types import CallbackQuery,Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import WITHDRAW_CHANNEL_ID
router=Router()
class W(StatesGroup): amount=State();method=State();account=State()
@router.callback_query(F.data=='withdraw')
async def start(c,state):
 p=await get_pool(); ok=await p.fetchrow("SELECT earnings FROM users WHERE user_id=$1 AND is_creator AND creator_status='approved'",c.from_user.id)
 if not ok:return await c.answer('Hanya Creator.',show_alert=True)
 enabled=str(await p.fetchval("SELECT value FROM settings WHERE key='withdraw_enabled'") or 'on')=='on'
 if not enabled:return await c.answer('Withdraw sedang ditutup.',show_alert=True)
 await c.answer(); await state.set_state(W.amount); await c.message.answer(f"💸 Saldo tersedia: Rp{int(ok['earnings'] or 0):,}\n\nKirim nominal WD.".replace(',','.'))
@router.message(W.amount)
async def amount(m,state):
 try:a=float((m.text or '').replace('.','').replace(',',''))
 except:return await m.answer('❌ Nominal tidak valid.')
 bal=float(await (await get_pool()).fetchval("SELECT earnings FROM users WHERE user_id=$1",m.from_user.id) or 0)
 if a<=0 or a>bal:return await m.answer('❌ Saldo tidak cukup.')
 await state.update_data(amount=a); await state.set_state(W.method); await m.answer('Kirim metode WD (DANA/OVO/Bank).')
@router.message(W.method)
async def method(m,state): await state.update_data(method=(m.text or '').strip()); await state.set_state(W.account); await m.answer('Kirim nomor rekening/e-wallet.')
@router.message(W.account)
async def account(m,state):
 d=await state.get_data(); p=await get_pool()
 async with p.acquire() as c:
  async with c.transaction():
   r=await c.fetchrow("UPDATE users SET earnings=earnings-$1 WHERE user_id=$2 AND earnings>=$1 RETURNING earnings",d['amount'],m.from_user.id)
   if not r:return await m.answer('❌ Saldo berubah, coba lagi.')
   await c.execute("INSERT INTO withdraws(user_id,amount,method,account) VALUES($1,$2,$3,$4)",m.from_user.id,d['amount'],d['method'],m.text.strip())
 await state.clear(); await m.answer('✅ Pengajuan WD berhasil. Menunggu admin.')
 if WITHDRAW_CHANNEL_ID:
  try: await m.bot.send_message(WITHDRAW_CHANNEL_ID,f"💸 WITHDRAW\n\n🆔 ID: {m.from_user.id}\n💰 Nominal: Rp{int(d['amount']):,}\n🏦 Metode: {d['method']}\n📌 Status: PENDING".replace(',','.'))
  except:pass
