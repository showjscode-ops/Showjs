
from aiogram import Router,F
import asyncio
from collections import defaultdict
from aiogram.filters import Command
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,BufferedInputFile,Message
import html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from config import POINT_PACKAGES,STAR_PACKAGES,DEPOSIT_PACKAGES,OWNER_ID,ADMIN_IDS,TRANSACTION_CHANNEL_URL,CREATOR_REGISTRATION_FEE_IDR,CREATOR_RENEWAL_PERCENT
from database import get_pool
from utils.payments import create_purchase,qr_bytes,enabled,save_payment_message_id
router=Router()

# Per-user payment creation lock: Telegram may deliver multiple rapid callback
# updates when the Buy button is tapped repeatedly. Serialize them so only one
# QR message is created/sent. DB idempotency still protects across processes.
_PAYMENT_LOCKS = defaultdict(asyncio.Lock)

class ManualProofState(StatesGroup):
    proof=State()
    qris=State()

async def is_admin_user(uid):
    # Accept OWNER_ID / ADMINS from Railway and DB is_admin.
    if int(uid) == int(OWNER_ID or 0) or int(uid) in ADMIN_IDS:
        return True
    try:
        p = await get_pool()
        return bool(await p.fetchval("SELECT COALESCE(is_admin,FALSE) FROM users WHERE user_id=$1::BIGINT", int(uid)))
    except Exception:
        return False

def admin(uid): return uid==OWNER_ID or uid in ADMIN_IDS
def fmt(n): return f"Rp{int(n):,}".replace(',','.')

@router.callback_query(F.data=='buy_points')
async def buy_points(c):
 rows=[[InlineKeyboardButton(text=f"🪙 {q} Poin • {fmt(v)}",callback_data=f"choosepay:points:{q}:{v}")] for q,v in POINT_PACKAGES.items()]
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
 await c.message.edit_text('🪙 <b>BUY POIN</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data=='buy_stars')
async def buy_stars(c):
 rows=[[InlineKeyboardButton(text=f"⭐ {q} Star • {fmt(v)}",callback_data=f"choosepay:stars:{q}:{v}")] for q,v in STAR_PACKAGES.items()]
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
 await c.message.edit_text('⭐ <b>BUY STAR</b>\n\nPilih paket:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data=='deposit')
async def deposit(c):
 rows=[[InlineKeyboardButton(text=fmt(v),callback_data=f'depamt:{v}')] for v in DEPOSIT_PACKAGES.values()]
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
 await c.message.edit_text('💳 <b>DEPOSIT SALDO</b>\n\nPilih nominal:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('depamt:'))
async def depamt(c):
 amount=int(c.data.split(':')[1]); rows=[]
 if await enabled('bayargg'): rows.append([InlineKeyboardButton(text='QR 2',callback_data=f'deppay:bayargg:{amount}')])
 if await enabled('cashi'): rows.append([InlineKeyboardButton(text='QR 1',callback_data=f'deppay:cashi:{amount}')])
 if await enabled('manual'): rows.append([InlineKeyboardButton(text='QR Manual',callback_data=f'deppay:manual:{amount}')])
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='deposit')])
 await c.message.edit_text(f'💳 <b>PAY DEPOSIT</b>\n\nNominal: <b>{fmt(amount)}</b>\nPilih pembayaran:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('deppay:'))
async def deppay(c,state:FSMContext):
 _,provider,amount=c.data.split(':'); amount=int(amount)
 if provider=='manual':
    qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
    if not qr:return await c.answer('❌ QR manual belum dipasang admin.',show_alert=True)
    p=await get_pool()
    row=await p.fetchrow("""INSERT INTO manual_deposits(user_id,amount,target_type,quantity,status)
      VALUES($1,$2,'deposit',1,'pending') RETURNING id""",c.from_user.id,amount)
    msg=await c.message.answer_photo(
        qr,caption=f'🧾 <b>QR MANUAL</b>\n\nNominal: <b>{fmt(amount)}</b>\n\nSetelah membayar, tekan <b>Cek Pembayaran</b> lalu kirim screenshot bukti.',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'mancheck:{row["id"]}')],
            [InlineKeyboardButton(text='❌ Batal',callback_data=f'mancancel:{row["id"]}')]
        ])
    )
    await p.execute("UPDATE manual_deposits SET qr_message_id=$1 WHERE id=$2",msg.message_id,row["id"])
    return
 r,status=await create_purchase(c.from_user.id,'deposit',1,amount,provider,c.from_user.full_name)
 if not r:return await c.answer('❌ Pembayaran sedang ditutup.',show_alert=True)
 data=qr_bytes(r.get('qr_string')); text=f'💳 <b>DEPOSIT</b>\n\n💰 {fmt(amount)}\n🏦 {"QR 2" if provider=="bayargg" else "QR 1"}\n🧾 <code>{r["invoice_id"]}</code>\n\nSaldo akan masuk otomatis setelah pembayaran terverifikasi.'
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'paycheck:{r["invoice_id"]}')],[InlineKeyboardButton(text='❌ Batal',callback_data=f'paycancel:{r["invoice_id"]}')]])
 if data: await c.message.answer_photo(BufferedInputFile(data,filename='deposit.png'),caption=text,parse_mode='HTML',reply_markup=kb)
 else: await c.message.answer(text,parse_mode='HTML',reply_markup=kb)


@router.callback_query(F.data=='creator_buy')
async def creator_buy(c):
    rows=[]
    if await enabled('bayargg'): rows.append([InlineKeyboardButton(text='QR 2',callback_data='creatorpay:bayargg')])
    if await enabled('cashi'): rows.append([InlineKeyboardButton(text='QR 1',callback_data='creatorpay:cashi')])
    if await enabled('manual'): rows.append([InlineKeyboardButton(text='QR Manual',callback_data='creatorpay:manual')])
    rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='creator_apply')])
    await c.message.edit_text('👑 <b>PEMBAYARAN CREATOR</b>\n\nBiaya Creator: <b>Rp200.000</b> jika baru, atau <b>30% (Rp60.000)</b> untuk akun Creator sebelumnya.\n\nPilih metode pembayaran:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('creatorpay:'))
async def creatorpay(c,state:FSMContext):
    provider=c.data.split(':',1)[1]
    p0=await get_pool()
    existing=await p0.fetchrow("SELECT creator_status,creator_previous FROM users WHERE user_id=$1",c.from_user.id)
    base=int(CREATOR_REGISTRATION_FEE_IDR)
    amount=int(base*CREATOR_RENEWAL_PERCENT/100) if existing and (existing['creator_previous'] or existing['creator_status']=='approved') else base
    if not await enabled(provider):
        return await c.answer('❌ Metode pembayaran sedang ditutup oleh admin.',show_alert=True)
    if provider=='manual':
        qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
        if not qr:return await c.answer('❌ QR manual belum dipasang admin.',show_alert=True)
        p=await get_pool()
        row=await p.fetchrow("INSERT INTO manual_deposits(user_id,amount,target_type,quantity,status) VALUES($1,$2,'creator',1,'pending') RETURNING id",c.from_user.id,amount)
        msg=await c.message.answer_photo(qr,caption='👑 <b>QR MANUAL CREATOR</b>\n\n💰 Rp200.000\n\nSetelah membayar, tekan Cek Pembayaran lalu kirim screenshot bukti.',parse_mode='HTML',
          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'mancheck:{row["id"]}')],
            [InlineKeyboardButton(text='❌ Batal',callback_data=f'mancancel:{row["id"]}')]
          ]))
        await p.execute("UPDATE manual_deposits SET qr_message_id=$1 WHERE id=$2",msg.message_id,row["id"])
        return
    r,status=await create_purchase(c.from_user.id,'creator',1,amount,provider,c.from_user.full_name)
    if not r:
        return await c.answer('❌ Gagal membuat pembayaran. Coba lagi.',show_alert=True)
    data=qr_bytes(r.get('qr_string'))
    text=f'👑 <b>CREATOR PAYMENT</b>\n\n💰 Rp{amount:,}'.replace(',', '.')+f'\n🏦 {"QR 2" if provider=="bayargg" else "QR 1"}\n🧾 <code>{r["invoice_id"]}</code>\n\nSetelah membayar, tekan Cek Pembayaran.'
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'paycheck:{r["invoice_id"]}')],
      [InlineKeyboardButton(text='❌ Batal',callback_data=f'paycancel:{r["invoice_id"]}')]
    ])
    if data: await c.message.answer_photo(BufferedInputFile(data,filename='creator-payment.png'),caption=text,parse_mode='HTML',reply_markup=kb)
    else: await c.message.answer(text,parse_mode='HTML',reply_markup=kb)

@router.callback_query(F.data.startswith('choosepay:'))
async def choose(c):
 _,typ,qty,amount=c.data.split(':'); payload=f'{typ}:{qty}:{amount}'; rows=[]
 if await enabled('bayargg'): rows.append([InlineKeyboardButton(text='QR 2',callback_data=f'provider:{payload}:bayargg')])
 if await enabled('cashi'): rows.append([InlineKeyboardButton(text='QR 1',callback_data=f'provider:{payload}:cashi')])
 if await enabled('manual'): rows.append([InlineKeyboardButton(text='QR Manual',callback_data=f'manualpkg:{payload}')])
 rows.append([InlineKeyboardButton(text='🔙 Kembali',callback_data='home')])
 await c.message.edit_text('💳 <b>PILIH PEMBAYARAN</b>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('provider:'))
async def provider(c):
 parts = (c.data or '').split(':')
 if len(parts) != 5 or parts[0] != 'provider':
  return await c.answer('❌ Data pembayaran tidak valid. Silakan pilih paket lagi.', show_alert=True)
 _, typ, qty, amount, provider_name = parts
 try:
  qty_i = int(qty)
  amount_i = int(amount)
 except ValueError:
  return await c.answer('❌ Data nominal pembayaran tidak valid.', show_alert=True)
 provider_name = provider_name.strip().lower()
 if provider_name not in {'bayargg', 'cashi'}:
  return await c.answer('❌ Provider pembayaran tidak valid.', show_alert=True)
 if not await enabled(provider_name):
  return await c.answer('❌ Provider sedang ditutup oleh admin.', show_alert=True)

 key=(c.from_user.id,typ,qty_i,amount_i,provider_name)
 async with _PAYMENT_LOCKS[key]:
  r,status=await create_purchase(c.from_user.id, typ, qty_i, amount_i, provider_name, c.from_user.full_name)
  if not r:
   msg = (
    '❌ Pembayaran sedang ditutup.' if status == 'disabled'
    else '❌ Nominal QR 2 harus Rp5.000–Rp500.000.' if status == 'invalid_amount'
    else '❌ Gagal menyimpan transaksi pembayaran. Coba lagi.'
   )
   return await c.answer(msg, show_alert=True)

  # If this invoice already has a Telegram payment message, do not send it again.
  # This is what stops 2x/3x/4x QR messages after rapid repeated taps.
  if r.get('reused') and r.get('payment_message_id'):
   await c.answer('ℹ️ QR pembayaran yang sama sudah dikirim. Silakan gunakan QR tersebut.', show_alert=True)
   try:
    await c.message.edit_reply_markup(reply_markup=None)
   except Exception:
    pass
   return

  data=qr_bytes(r.get('qr_string')); text=f'💳 <b>PAYMENT</b>\n\n📦 {qty_i}\n💰 {fmt(amount_i)}\n🏦 {"QR 2" if provider_name=="bayargg" else "QR 1"}\n🧾 <code>{r["invoice_id"]}</code>'
  kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'paycheck:{r["invoice_id"]}')],[InlineKeyboardButton(text='❌ Batal',callback_data=f'paycancel:{r["invoice_id"]}')]])
  if data:
   msg=await c.message.answer_photo(BufferedInputFile(data,filename='payment.png'),caption=text,parse_mode='HTML',reply_markup=kb)
  else:
   msg=await c.message.answer(text,parse_mode='HTML',reply_markup=kb)
  await save_payment_message_id(r['invoice_id'],msg.message_id)
  try:
   await c.message.edit_reply_markup(reply_markup=None)
  except Exception:
   pass
  await c.answer('✅ QR pembayaran dikirim. Gunakan QR yang sama sampai pembayaran selesai.')


@router.callback_query(F.data.startswith('paycheck:'))
async def paycheck(c):
    invoice = c.data.split(':',1)[1].strip()
    if not invoice:
        return await c.answer('❌ ID pembayaran tidak valid.', show_alert=True)
    p=await get_pool()
    row=await p.fetchrow("SELECT * FROM purchases WHERE invoice_id=$1 AND user_id=$2", invoice, c.from_user.id)
    if not row:
        return await c.answer('❌ Pembayaran tidak ditemukan.', show_alert=True)
    if row['status']=='paid':
        return await c.answer('✅ Pembayaran sudah berhasil diproses.', show_alert=True)
    if row['status'] in {'cancelled','canceled','failed','expired'}:
        return await c.answer(f'❌ Pembayaran sudah {row["status"]}.', show_alert=True)
    from utils.bayargg import BayarGG
    from utils.cashi import Cashi
    result = await (BayarGG.check_payment(invoice) if row['provider']=='bayargg' else Cashi.check_payment(invoice))
    if not result:
        return await c.answer('⚠️ Gagal mengecek pembayaran. Coba lagi.', show_alert=True)
    status=str(result.get('status') or '').lower()
    if status in {'paid','success','completed','settled'}:
        from utils.payments import finalize_purchase
        ok=await finalize_purchase(invoice, result.get('amount') or None)
        if ok:
            return await c.answer('✅ Pembayaran berhasil diproses!', show_alert=True)
        return await c.answer('⚠️ Pembayaran terdeteksi berhasil, tetapi proses saldo belum selesai. Coba cek lagi.', show_alert=True)
    if status in {'cancelled','canceled','failed','expired'}:
        await p.execute("UPDATE purchases SET status=$1 WHERE invoice_id=$2 AND status='pending'", status, invoice)
        return await c.answer(f'❌ Pembayaran {status}.', show_alert=True)
    return await c.answer('⏳ Pembayaran belum diterima. Setelah transfer, tekan Cek Pembayaran lagi.', show_alert=True)

@router.callback_query(F.data.startswith('paycancel:'))
async def paycancel(c):
    invoice = c.data.split(':',1)[1].strip()
    p=await get_pool()
    row=await p.fetchrow("SELECT id,status FROM purchases WHERE invoice_id=$1 AND user_id=$2",invoice,c.from_user.id)
    if not row:
        return await c.answer('❌ Pembayaran tidak ditemukan.', show_alert=True)
    if row['status']=='paid':
        return await c.answer('✅ Pembayaran sudah berhasil, tidak bisa dibatalkan.', show_alert=True)
    if row['status']!='pending':
        return await c.answer(f'❌ Pembayaran sudah {row["status"]}.', show_alert=True)
    # Do not invalidate the provider invoice. We only hide/remove the QR
    # message; a later Buy action can reuse the same still-valid QR/invoice.
    await c.answer('❌ Pembayaran dibatalkan. Jika QR belum expired, pembelian berikutnya akan memakai QR yang sama.', show_alert=True)
    try:
        await c.bot.delete_message(c.message.chat.id,c.message.message_id)
    except Exception:
        try: await c.message.edit_reply_markup(reply_markup=None)
        except Exception: pass

@router.callback_query(F.data.startswith('manualpkg:'))
async def manualpkg(c,state:FSMContext):
 _,payload=c.data.split(':',1); typ,qty,amount=payload.split(':'); amount=int(amount)
 qr=await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='manual_qr_file_id'")
 if not qr:return await c.answer('❌ QR manual belum dipasang admin.',show_alert=True)
 p=await get_pool()
 row=await p.fetchrow("""INSERT INTO manual_deposits(user_id,amount,target_type,quantity,status)
 VALUES($1,$2,$3,$4,'pending') RETURNING id""",c.from_user.id,amount,typ,int(qty))
 msg=await c.message.answer_photo(
   qr,caption=f'🧾 <b>QR MANUAL</b>\n\n💰 {fmt(amount)}\n\nSetelah membayar, tekan <b>Cek Pembayaran</b> lalu kirim screenshot bukti.',
   parse_mode='HTML',
   reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='🔄 Cek Pembayaran',callback_data=f'mancheck:{row["id"]}')],
      [InlineKeyboardButton(text='❌ Batal',callback_data=f'mancancel:{row["id"]}')]
   ])
 )
 await p.execute("UPDATE manual_deposits SET qr_message_id=$1 WHERE id=$2",msg.message_id,row["id"])


@router.callback_query(F.data.startswith('mancheck:'))
async def mancheck(c,state:FSMContext):
    did=int(c.data.split(':',1)[1]); p=await get_pool()
    row=await p.fetchrow("SELECT * FROM manual_deposits WHERE id=$1 AND user_id=$2",did,c.from_user.id)
    if not row: return await c.answer('❌ Pembayaran manual tidak ditemukan.',show_alert=True)
    if row['status']!='pending': return await c.answer(f'❌ Status pembayaran: {row["status"]}.',show_alert=True)
    await state.set_state(ManualProofState.proof)
    await state.update_data(kind=row['target_type'] or 'deposit',quantity=row['quantity'] or 0,amount=int(row['amount']),target_code=row['target_code'],manual_id=did)
    await c.answer('📸 Kirim screenshot bukti pembayaran sekarang.',show_alert=True)
    try:
        await c.message.edit_caption(
            caption=f'🧾 <b>QR MANUAL</b>\n\n💰 {fmt(row["amount"])}\n🧾 ID: <code>{did}</code>\n\n📸 Silakan kirim screenshot bukti pembayaran.',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❌ Batal',callback_data=f'mancancel:{did}')]])
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith('mancancel:'))
async def mancancel(c,state:FSMContext):
    did=int(c.data.split(':',1)[1]); p=await get_pool()
    row=await p.fetchrow("SELECT * FROM manual_deposits WHERE id=$1 AND user_id=$2",did,c.from_user.id)
    if not row: return await c.answer('❌ Pembayaran tidak ditemukan.',show_alert=True)
    if row['status']=='approved': return await c.answer('✅ Pembayaran sudah disetujui.',show_alert=True)
    await p.execute("UPDATE manual_deposits SET status='cancelled',processed_at=NOW() WHERE id=$1 AND status='pending'",did)
    await state.clear()
    if row['qr_message_id']:
        try: await c.bot.delete_message(c.message.chat.id,row['qr_message_id'])
        except Exception: pass
    await c.answer('❌ Pembayaran manual dibatalkan dan QR dihapus.',show_alert=True)


@router.message(ManualProofState.proof)
async def proof(m:Message,state:FSMContext):
    if not (m.photo or m.document):
        return await m.answer('❌ Kirim screenshot/foto bukti pembayaran.')
    d=await state.get_data(); p=await get_pool()
    fid=m.photo[-1].file_id if m.photo else m.document.file_id
    ftype='photo' if m.photo else 'document'
    manual_id=d.get('manual_id')
    if manual_id:
        row=await p.fetchrow("SELECT * FROM manual_deposits WHERE id=$1 AND user_id=$2 AND status='pending'",int(manual_id),m.from_user.id)
    else:
        row=await p.fetchrow("""SELECT * FROM manual_deposits WHERE user_id=$1 AND amount=$2 AND status='pending' AND proof_file_id IS NULL
          AND COALESCE(target_code,'')=COALESCE($3,'') ORDER BY id DESC LIMIT 1""",
          m.from_user.id,int(d.get('amount',0)),d.get('target_code'))
    if not row:
        return await m.answer('❌ Pembayaran manual tidak ditemukan atau sudah diproses.')
    await p.execute("""UPDATE manual_deposits SET proof_file_id=$1,proof_type=$2,proof_message_id=$3,target_type=$4,quantity=$5 WHERE id=$6""",
                    fid,ftype,m.message_id,d.get('kind') or row['target_type'],d.get('quantity',row['quantity'] or 0),row['id'])
    await state.clear()
    await m.answer(f'✅ Bukti pembayaran diterima.\n🧾 ID: <code>{row["id"]}</code>\n\nMenunggu persetujuan admin.',parse_mode='HTML')
    for aid in [OWNER_ID,*ADMIN_IDS]:
        try:
            cap=(f'🔔 <b>MANUAL PAYMENT PROOF</b>\n\n'
                 f'🧾 ID: <code>{row["id"]}</code>\n'
                 f'🆔 User: <code>{m.from_user.id}</code>\n'
                 f'💰 {fmt(row["amount"])}\n'
                 f'📦 Type: <b>{html.escape(str(d.get("kind") or row["target_type"] or "deposit"))}</b>')
            buttons=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='✅ Approve',callback_data=f'manapprove:{row["id"]}'),
                InlineKeyboardButton(text='❌ Reject',callback_data=f'manreject:{row["id"]}')
            ]])
            if ftype=='photo':
                await m.bot.send_photo(aid,fid,caption=cap,parse_mode='HTML',reply_markup=buttons)
            else:
                await m.bot.send_document(aid,fid,caption=cap,parse_mode='HTML',reply_markup=buttons)
        except Exception:
            pass

@router.message(Command('getqrisid'))
async def getqrisid(m,state:FSMContext):
 if not admin(m.from_user.id): return
 await state.set_state(ManualProofState.qris)
 await m.answer('🧾 <b>SET QR MANUAL</b>\n\nKirim gambar QR yang ingin digunakan sebagai pembayaran manual.',parse_mode='HTML')

@router.message(ManualProofState.qris)
async def save_qris(m,state:FSMContext):
 if not admin(m.from_user.id): return
 if not m.photo:return await m.answer('❌ Kirim gambar QR.')
 fid=m.photo[-1].file_id
 await (await get_pool()).execute("UPDATE settings SET value=$1 WHERE key='manual_qr_file_id'",fid)
 await state.clear(); await m.answer('✅ QR manual berhasil disimpan.')

@router.callback_query(F.data.startswith('manapprove:'))
async def approve(c):
 if not admin(c.from_user.id): return await c.answer('No access',show_alert=True)
 did=int(c.data.split(':')[1]); p=await get_pool()
 async with p.acquire() as conn:
  async with conn.transaction():
   r=await conn.fetchrow("SELECT * FROM manual_deposits WHERE id=$1 FOR UPDATE",did)
   if not r or r['status']!='pending': return await c.answer('Sudah diproses.',show_alert=True)
   await conn.execute("UPDATE manual_deposits SET status='approved',admin_id=$1,processed_at=NOW() WHERE id=$2",c.from_user.id,did)
   if r['target_code']:
    f=await conn.fetchrow("SELECT owner_id,price_idr FROM files WHERE code=$1 AND active=TRUE",r['target_code'])
    if f:
     income=int(r['amount'])*70//100
     await conn.execute("UPDATE files SET views=views+1 WHERE code=$1",r['target_code'])
     await conn.execute("UPDATE users SET total_unlocks=total_unlocks+1 WHERE user_id=$2",r['user_id'])
     if int(f['owner_id'])!=int(r['user_id']): await conn.execute("UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1,points=points+1 WHERE user_id=$2",income,f['owner_id'])
     await conn.execute("""INSERT INTO unlock_transactions(user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at) VALUES($1,$2,$3,'qr',$4,1,$5,NOW()+INTERVAL '24 hours')""",r['user_id'],f['owner_id'],r['target_code'],r['amount'],income)
   elif r['target_type']=='points':
    await conn.execute("UPDATE users SET points=points+$1 WHERE user_id=$2",r['quantity'],r['user_id'])
   elif r['target_type']=='stars':
    await conn.execute("UPDATE users SET stars=stars+$1 WHERE user_id=$2",r['quantity'],r['user_id'])
   elif r['target_type']=='vip':
    await conn.execute("""
     UPDATE users
     SET vip=TRUE,
         vip_until=GREATEST(COALESCE(vip_until,NOW()),NOW())+($1||' days')::interval,
         vip_plan_days=$1,
         vip_daily_limit=CASE
             WHEN $1=1 THEN 2
             WHEN $1=3 THEN 4
             WHEN $1=5 THEN 6
             WHEN $1=7 THEN 7
             WHEN $1=10 THEN 10
             WHEN $1=15 THEN 15
             WHEN $1=30 THEN 30
             ELSE GREATEST($1,1)
         END
     WHERE user_id=$2
    """,int(r['quantity']),r['user_id'])
   elif r['target_type']=='creator':
    await conn.execute("UPDATE users SET creator_status=CASE WHEN creator_status='approved' THEN creator_status ELSE 'pending' END WHERE user_id=$1",r['user_id'])
   else:
    await conn.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2",r['amount'],r['user_id'])
 # Remove the user's manual QR after approval.
 try:
  if r['qr_message_id']:
   await c.bot.delete_message(int(r['user_id']),int(r['qr_message_id']))
 except Exception:
  pass
 await c.answer('Approved')
 try:
  await c.message.edit_reply_markup(reply_markup=None)
 except Exception:
  pass
 try:
  from config import TRANSACTION_CHAT_ID
  if TRANSACTION_CHAT_ID:
   await c.bot.send_message(TRANSACTION_CHAT_ID,
     f'💳 <b>TRANSACTION SUCCESS</b>\n\n👤 User ID: <code>{r["user_id"]}</code>\n📦 Type: <b>Manual {html.escape(str(r["target_type"] or "deposit"))}</b>\n🔢 Quantity: <b>{float(r["quantity"] or 0):g}</b>\n💰 Amount: <b>{fmt(r["amount"])}</b>\n🏦 Provider: <b>QR MANUAL</b>',
     parse_mode='HTML')
 except Exception:
  pass
 try:
  from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
  if r['target_code']:
   await c.bot.send_message(r['user_id'],f'✅ Pembayaran manual disetujui.\n🔑 Code: <code>{r["target_code"]}</code>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📥 Buka Code',callback_data=f'getcode:{r["target_code"]}')]]))
  elif r['target_type']=='creator':
   await c.bot.send_message(r['user_id'],'✅ Pembayaran Creator disetujui. 👑 Pendaftaran kamu sudah tercatat dan menunggu verifikasi admin.',parse_mode='HTML')
  else:
   await c.bot.send_message(r['user_id'],'✅ Pembayaran manual disetujui. Saldo/paket sudah ditambahkan.')
 except: pass

@router.callback_query(F.data.startswith('manreject:'))
async def reject(c):
 if not admin(c.from_user.id): return await c.answer('No access',show_alert=True)
 did=int(c.data.split(':')[1]); p=await get_pool()
 r=await p.fetchrow("UPDATE manual_deposits SET status='rejected',admin_id=$1,processed_at=NOW() WHERE id=$2 AND status='pending' RETURNING user_id",c.from_user.id,did)
 await c.answer('Rejected' if r else 'Sudah diproses.'); 
 if r:
  try:
   full=await p.fetchrow("SELECT qr_message_id FROM manual_deposits WHERE id=$1",did)
   if full and full['qr_message_id']:
    await c.bot.delete_message(int(r['user_id']),int(full['qr_message_id']))
  except: pass
  try: await c.bot.send_message(r['user_id'],'❌ Pembayaran manual ditolak. Silakan lakukan pembayaran baru jika diperlukan.')
  except: pass
