
from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import ADMIN_IDS,TRIAL_POINTS,TRIAL_STARS,PAID_CODE_MIN_IDR,PAID_CODE_MAX_IDR
from utils.admin_access import admin_access, is_config_admin, admin_env_debug
from utils.b2_storage import b2_pool
from utils.callback_loading import loading
import html,asyncio,re

router=Router()

@router.message(Command("admincheck"))
async def admincheck(m):
    d=admin_env_debug(m.from_user.id)
    db=False
    try:
        p=await get_pool()
        row=await p.fetchrow("SELECT COALESCE(is_admin,FALSE) AS is_admin FROM users WHERE user_id=$1::BIGINT",int(m.from_user.id))
        db=bool(row and row["is_admin"])
    except Exception as e:
        await m.answer(f"⚠️ DB admin check error: <code>{html.escape(str(e)[:300])}</code>",parse_mode="HTML")
        return
    access=d["is_admin_env"] or db
    await m.answer(
        "🔎 <b>ADMIN CHECK</b>\n\n"
        f"🆔 ID: <code>{d['user_id']}</code>\n"
        f"🔐 ENV: <b>{'YES' if d['is_admin_env'] else 'NO'}</b>\n"
        f"🗄 DB is_admin: <b>{'YES' if db else 'NO'}</b>\n"
        f"👑 Access: <b>{'YES' if access else 'NO'}</b>\n\n"
        f"OWNER_ID: <code>{html.escape(d['owner_id'] or '-')}</code>\n"
        f"ADMINS: <code>{html.escape(d['admins'] or '-')}</code>\n"
        f"ADMIN_IDS: <code>{html.escape(d['admin_ids'] or '-')}</code>",
        parse_mode="HTML",
    )

@router.message(Command('admin'))
async def admin_command(m):
    if not await admin_access(m.from_user.id):
        return await m.answer(f'❌ Kamu tidak memiliki akses admin.\n\n🆔 Telegram ID kamu: <code>{m.from_user.id}</code>\n\nMasukkan ID ini ke OWNER_ID atau ADMINS/ADMIN_IDS di Railway, lalu redeploy.', parse_mode='HTML')
    p=await get_pool()
    try:
        users=await p.fetchval("SELECT COUNT(*) FROM users")
        codes=await p.fetchval("SELECT COUNT(*) FROM files WHERE active=TRUE")
        pending=await p.fetchval("SELECT COUNT(*) FROM manual_deposits WHERE status='pending'")
    except Exception:
        users=codes=pending=0
    await m.answer(
        f"👑 <b>ADMIN PANEL</b>\n\n👥 Users: <b>{users}</b>\n🔑 Active Code: <b>{codes}</b>\n🧾 Manual Pending: <b>{pending}</b>",
        parse_mode='HTML',
        reply_markup=kb()
    )
class AdminState(StatesGroup):
    creator=State(); broadcast=State(); edit_code=State(); edit_title=State(); edit_tags=State(); edit_price=State(); user_action=State(); move=State(); grant_open_user=State(); grant_open_code=State(); role_user=State()
    b2_name=State(); b2_region=State(); b2_bucket=State(); b2_key_id=State(); b2_app_key=State()

def admin(uid): return is_config_admin(uid)
async def val(key): return str(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key=$1",key) or "off")
async def setval(key,value): await (await get_pool()).execute("INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",key,str(value))

def kb():
 return InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text='💳 Pembayaran',callback_data='adm:payments'),InlineKeyboardButton(text='📢 Broadcast',callback_data='adm:broadcast')],
  [InlineKeyboardButton(text='🗂 Code',callback_data='adm:codes'),InlineKeyboardButton(text='👥 Users',callback_data='adm:users')],
  [InlineKeyboardButton(text='🔓 Buka Code untuk User',callback_data='adm:grantopen'),InlineKeyboardButton(text='👤 Atur Role User',callback_data='adm:roles')],
  [InlineKeyboardButton(text='🗄 B2 Storage',callback_data='adm:b2'),InlineKeyboardButton(text='⚙️ Bot Control',callback_data='adm:control')],
  [InlineKeyboardButton(text='🧾 Manual Payment',callback_data='adm:manual'),InlineKeyboardButton(text='📊 Statistics',callback_data='adm:stats')],
  [InlineKeyboardButton(text='🚨 Bot Errors',callback_data='adm:errors')],
  [InlineKeyboardButton(text='🔄 Refresh',callback_data='adm:panel')]])

async def panel_text():
    p=await get_pool()
    async def count(sql):
        try: return await p.fetchval(sql) or 0
        except Exception: return 0
    users=await count("SELECT COUNT(*) FROM users")
    codes=await count("SELECT COUNT(*) FROM files WHERE active=TRUE")
    pending=await count("SELECT COUNT(*) FROM manual_deposits WHERE status='pending'")
    return f"👑 <b>ADMIN PANEL</b>\n\n👥 Users: <b>{users}</b>\n🔑 Active Code: <b>{codes}</b>\n🧾 Manual Pending: <b>{pending}</b>\n\n🗄 B2: <b>{len(b2_pool.accounts)}/10</b>"

@router.message(Command('panel'))
async def panel(m):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 await m.answer(await panel_text(),parse_mode='HTML',reply_markup=kb())

@router.callback_query(F.data=='adm:panel')
async def refresh(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 await c.message.edit_text(await panel_text(),parse_mode='HTML',reply_markup=kb())

@router.callback_query(F.data=='adm:payments')
async def payments(c):
 if not await admin_access(c.from_user.id): return
 p=await get_pool()
 rows=[]
 for key,label in [('payment_bayargg_enabled','⚡ BayarGG'),('payment_cashi_enabled','💳 Cashi'),('payment_manual_enabled','🧾 QR Manual'),('payment_balance_enabled','💰 Saldo')]:
  state=(await val(key)).upper()
  rows.append([InlineKeyboardButton(text=f'{label}: {state}',callback_data=f'admtoggle:{key}')])
 rows.append([InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')])
 await c.message.edit_text('💳 <b>PAYMENT CONTROL</b>\n\nAktif/nonaktifkan 4 metode pembayaran.',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('admtoggle:'))
async def admtoggle(c):
 if not await admin_access(c.from_user.id): return
 key=c.data.split(':',1)[1]; old=await val(key); await setval(key,'off' if old=='on' else 'on'); await payments(c)

@router.callback_query(F.data=='adm:control')
async def control(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 rows=[]
 for key,label in [('maintenance','🛠 Maintenance'),('trial_enabled','🧪 Trial')]:
  rows.append([InlineKeyboardButton(text=f'{label}: {(await val(key)).upper()}',callback_data=f'admtoggle2:{key}')])
 rows += [[InlineKeyboardButton(text='⏱ VIP Delay 30m',callback_data='admset:vipdelay')],[InlineKeyboardButton(text='⚡ Media Send Delay',callback_data='admset:mediadelay')],[InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]]
 await c.message.edit_text('⚙️ <b>BOT CONTROL</b>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('admtoggle2:'))
async def admtoggle2(c):
 if not await admin_access(c.from_user.id): return
 key=c.data.split(':',1)[1]; old=await val(key); await setval(key,'off' if old=='on' else 'on'); await control(c)

@router.callback_query(F.data.startswith('admset:'))
async def admset(c,state:FSMContext):
 if not await admin_access(c.from_user.id): return
 typ=c.data.split(':')[1]; await state.set_state(AdminState.user_action)
 await state.update_data(setting='media_send_delay_ms' if typ=='mediadelay' else 'vip_code_delay_minutes')
 await c.message.answer('Kirim angka baru.')

@router.callback_query(F.data=='adm:stats')
async def stats(c):
 if not await admin_access(c.from_user.id): return
 p=await get_pool()
 r=await p.fetchrow("SELECT COUNT(*) users FROM users")
 f=await p.fetchrow("SELECT COUNT(*) codes,COALESCE(SUM(media_count),0) media,COALESCE(SUM(views),0) views FROM files")
 await c.message.edit_text(f"📊 <b>STATISTICS</b>\n\n👥 Users: {r['users']}\n🔑 Codes: {f['codes']}\n📦 Media: {f['media']}\n👁 Views: {f['views']}",parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]]))

@router.callback_query(F.data=='adm:b2')
async def b2menu(c):
 if not await admin_access(c.from_user.id): return
 await b2_pool.reload_from_db()
 p=await get_pool()
 preferred=int(await p.fetchval("SELECT value FROM settings WHERE key='preferred_b2_account'") or 0)
 rows=[]
 dbrows=await p.fetch("SELECT account_id,name,bucket,region,enabled FROM b2_storage_accounts ORDER BY account_id")
 dbmap={int(r['account_id']):r for r in dbrows}
 for a in b2_pool.accounts:
  star=' ⭐' if preferred==a.account_id else ''
  label=(a.name or a.bucket or f'B2 #{a.account_id}')[:28]
  rows.append([InlineKeyboardButton(text=f'🗄 #{a.account_id} {label}{star}',callback_data=f'b2select:{a.account_id}')])
  if a.account_id in dbmap:
   rows.append([InlineKeyboardButton(text=f'🗑 Hapus B2 #{a.account_id}',callback_data=f'b2del:{a.account_id}')])
 rows += [
   [InlineKeyboardButton(text='➕ Tambah Storage Backblaze',callback_data='b2add')],
   [InlineKeyboardButton(text='🔄 Ganti Storage / Target Upload',callback_data='b2choose')],
   [InlineKeyboardButton(text='🩺 Cek Semua',callback_data='b2health'),InlineKeyboardButton(text='📦 Kapasitas (MB)',callback_data='b2stats')],
   [InlineKeyboardButton(text='🔄 AUTO / FAILOVER',callback_data='b2auto')],
   [InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]
 ]
 await c.message.edit_text(
   f'🗄 <b>B2 STORAGE</b>\n\n'
   f'Configured: <b>{len(b2_pool.accounts)}/10</b>\n'
   f'➕ Storage baru bisa ditambahkan langsung dari panel ini tanpa membuka Railway.',
   parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
 )

@router.callback_query(F.data=='b2add')
async def b2add_start(c,state: FSMContext):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 p=await get_pool()
 used={int(r['account_id']) for r in await p.fetch("SELECT account_id FROM b2_storage_accounts")}
 used.update(a.account_id for a in b2_pool.accounts)
 free=next((i for i in range(1,11) if i not in used),None)
 if free is None:
  return await c.answer('❌ Maksimal 10 storage B2 sudah terpakai.',show_alert=True)
 await state.update_data(b2_account_id=free)
 await state.set_state(AdminState.b2_name)
 await c.message.answer(
   f'➕ <b>TAMBAH BACKBLAZE B2 #{free}</b>\n\n'
   'Kirim nama storage, contoh: <code>Backup Utama</code>',
   parse_mode='HTML'
 )
 await c.answer()

@router.message(AdminState.b2_name)
async def b2add_name(m,state: FSMContext):
 if not await admin_access(m.from_user.id): return
 name=(m.text or '').strip()
 if not name: return await m.answer('❌ Nama tidak boleh kosong.')
 await state.update_data(b2_name=name[:80])
 await state.set_state(AdminState.b2_region)
 await m.answer('🌎 Kirim <b>Region</b> Backblaze, contoh: <code>us-east-005</code>',parse_mode='HTML')

@router.message(AdminState.b2_region)
async def b2add_region(m,state: FSMContext):
 if not await admin_access(m.from_user.id): return
 region=(m.text or '').strip()
 if not re.match(r'^[A-Za-z0-9._-]{2,80}$',region):
  return await m.answer('❌ Region tidak valid.')
 await state.update_data(b2_region=region)
 await state.set_state(AdminState.b2_bucket)
 await m.answer('🪣 Kirim <b>Bucket Name</b> Backblaze.',parse_mode='HTML')

@router.message(AdminState.b2_bucket)
async def b2add_bucket(m,state: FSMContext):
 if not await admin_access(m.from_user.id): return
 bucket=(m.text or '').strip()
 if not bucket: return await m.answer('❌ Bucket tidak boleh kosong.')
 await state.update_data(b2_bucket=bucket[:200])
 await state.set_state(AdminState.b2_key_id)
 await m.answer('🔑 Kirim <b>Application Key ID</b>.',parse_mode='HTML')

@router.message(AdminState.b2_key_id)
async def b2add_key_id(m,state: FSMContext):
 if not await admin_access(m.from_user.id): return
 key=(m.text or '').strip()
 if not key: return await m.answer('❌ Key ID tidak boleh kosong.')
 await state.update_data(b2_key_id=key)
 await state.set_state(AdminState.b2_app_key)
 await m.answer('🔐 Kirim <b>Application Key</b>. Pesan ini hanya dipakai untuk menyimpan konfigurasi B2.',parse_mode='HTML')

@router.message(AdminState.b2_app_key)
async def b2add_app_key(m,state: FSMContext):
 if not await admin_access(m.from_user.id): return
 app_key=(m.text or '').strip()
 if not app_key: return await m.answer('❌ Application Key tidak boleh kosong.')
 d=await state.get_data()
 aid=int(d.get('b2_account_id') or 0)
 name=str(d.get('b2_name') or '')
 region=str(d.get('b2_region') or '')
 bucket=str(d.get('b2_bucket') or '')
 key_id=str(d.get('b2_key_id') or '')
 endpoint=f'https://s3.{region}.backblazeb2.com'
 p=await get_pool()
 try:
  await p.execute(
   '''INSERT INTO b2_storage_accounts(account_id,name,endpoint,region,bucket,key_id,application_key,enabled,updated_at)
      VALUES($1,$2,$3,$4,$5,$6,$7,TRUE,NOW())
      ON CONFLICT(account_id) DO UPDATE SET name=EXCLUDED.name,endpoint=EXCLUDED.endpoint,
        region=EXCLUDED.region,bucket=EXCLUDED.bucket,key_id=EXCLUDED.key_id,
        application_key=EXCLUDED.application_key,enabled=TRUE,updated_at=NOW()''',
   aid,name,endpoint,region,bucket,key_id,app_key
  )
  await b2_pool.reload_from_db()
  try:
   h=await b2_pool.health(aid)
   status=f'🟢 Terhubung • {h["latency_ms"]} ms'
  except Exception as exc:
   status=f'🟠 Tersimpan, tetapi tes koneksi gagal: {html.escape(str(exc)[:180])}'
  await state.clear()
  await m.answer(
   f'✅ <b>STORAGE B2 #{aid} DITAMBAHKAN</b>\n\n'
   f'🏷 {html.escape(name)}\n'
   f'🪣 <code>{html.escape(bucket)}</code>\n'
   f'🌎 <code>{html.escape(region)}</code>\n'
   f'{status}\n\n'
   'Storage sekarang bisa dipilih dari panel admin tanpa Railway.',
   parse_mode='HTML',
   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🗄 B2 Storage',callback_data='adm:b2')]])
  )
 except Exception as exc:
  await state.clear()
  await m.answer(f'❌ Gagal menyimpan B2: <code>{html.escape(str(exc)[:500])}</code>',parse_mode='HTML')

@router.callback_query(F.data.startswith('b2del:'))
async def b2del_confirm(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 aid=int(c.data.split(':',1)[1])
 p=await get_pool()
 r=await p.fetchrow("SELECT account_id,name,bucket FROM b2_storage_accounts WHERE account_id=$1",aid)
 if not r: return await c.answer('Storage ini bukan konfigurasi panel.',show_alert=True)
 await c.message.edit_text(
   f'⚠️ <b>HAPUS STORAGE B2 #{aid}?</b>\n\n'
   f'🏷 {html.escape(r["name"] or "-")}\n'
   f'🪣 <code>{html.escape(r["bucket"])}</code>\n\n'
   'Object yang sudah tersimpan di B2 <b>tidak akan dihapus</b>. Yang dihapus hanya konfigurasi akun dari panel.',
   parse_mode='HTML',
   reply_markup=InlineKeyboardMarkup(inline_keyboard=[
     [InlineKeyboardButton(text='⚠️ Ya, Hapus Konfigurasi',callback_data=f'b2delyes:{aid}')],
     [InlineKeyboardButton(text='❌ Batal',callback_data='adm:b2')]
   ])
 )

@router.callback_query(F.data.startswith('b2delyes:'))
async def b2del_yes(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 aid=int(c.data.split(':',1)[1])
 p=await get_pool()
 await p.execute("DELETE FROM b2_storage_accounts WHERE account_id=$1",aid)
 preferred=int(await p.fetchval("SELECT value FROM settings WHERE key='preferred_b2_account'") or 0)
 if preferred==aid: await setval('preferred_b2_account','0')
 await b2_pool.reload_from_db()
 await c.answer(f'B2 #{aid} dihapus.')
 await b2menu(c)

@router.callback_query(F.data.startswith('b2select:'))
async def b2select(c):
 if not await admin_access(c.from_user.id): return
 aid=int(c.data.split(':')[1]); await setval('preferred_b2_account',aid); await c.answer(f'B2 #{aid} menjadi target upload.'); await b2menu(c)

@router.callback_query(F.data=='b2choose')
async def b2choose(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 preferred=int(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='preferred_b2_account'") or 0)
 rows=[]
 for a in b2_pool.accounts:
  mark=' ✅ AKTIF' if preferred==a.account_id else ''
  rows.append([InlineKeyboardButton(text=f'🗄 B2 #{a.account_id} • {a.bucket}{mark}',callback_data=f'b2select:{a.account_id}')])
 rows.append([InlineKeyboardButton(text='🔄 AUTO / FAILOVER',callback_data='b2auto')])
 rows.append([InlineKeyboardButton(text='🔙 B2 Storage',callback_data='adm:b2')])
 await c.message.edit_text('🔄 <b>GANTI STORAGE BACKBLAZE</b>\n\nPilih B2 yang akan menjadi target utama upload.\n\nJika target gagal, sistem tetap mencoba storage B2 lain yang tersedia.',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data=='b2auto')
async def b2auto(c):
 if not await admin_access(c.from_user.id): return
 await setval('preferred_b2_account',0); await c.answer('AUTO / FAILOVER aktif.'); await b2menu(c)

@router.callback_query(F.data=='b2health')
async def b2health(c):
 if not await admin_access(c.from_user.id): return
 lines=['🩺 <b>B2 HEALTH</b>']
 for a in b2_pool.accounts:
  try:
   h=await b2_pool.health(a.account_id); lines.append(f"🟢 B2 #{a.account_id} • {h['latency_ms']} ms • {h['bucket']}")
  except Exception as e: lines.append(f"🔴 B2 #{a.account_id} • {str(e)[:80]}")
 await c.message.edit_text('\n'.join(lines),parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 B2',callback_data='adm:b2')]]))

@router.callback_query(F.data=='b2stats')
async def b2stats(c):
 if not await admin_access(c.from_user.id): return
 lines=['📦 <b>B2 CAPACITY</b>']
 for a in b2_pool.accounts:
  try:
   s=await b2_pool.stats(a.account_id); b=s['bytes']; mb=b/1024**2; gb=b/1024**3
   lines.append(f"🗄 B2 #{a.account_id} • {s['objects']} objects\n   📦 {mb:,.2f} MB • {gb:,.2f} GB")
  except Exception as e: lines.append(f"🔴 B2 #{a.account_id}: {str(e)[:80]}")
 await c.message.edit_text('\n'.join(lines),parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 B2',callback_data='adm:b2')]]))

@router.message(Command('moveb2'))
async def moveb2(m):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 parts=(m.text or '').split(maxsplit=3)
 if len(parts)!=4:return await m.answer('Format: <code>/moveb2 FROM TO CODE</code>',parse_mode='HTML')
 src,dst,code=int(parts[1]),int(parts[2]),parts[3]
 p=await get_pool(); f=await p.fetchrow("SELECT media FROM files WHERE code=$1",code)
 if not f:return await m.answer('❌ Code tidak ditemukan.')
 media=f['media'] if isinstance(f['media'],list) else __import__('json').loads(f['media'] or '[]')
 moved=0
 for item in media:
  if int(item.get('drive_account',0))==src:
   try:
    await b2_pool.move_object(src,dst,item['drive_file_id']); item['drive_account']=dst; moved+=1
   except: pass
 await p.execute("UPDATE files SET media=$1::jsonb WHERE code=$2",__import__('json').dumps(media),code)
 await m.answer(f'✅ Dipindahkan <b>{moved}</b> media dari B2 #{src} ke #{dst}.',parse_mode='HTML')

@router.callback_query(F.data=='adm:manual')
async def manual(c):
 if not await admin_access(c.from_user.id): return
 rows=await (await get_pool()).fetch("SELECT id,user_id,amount,status FROM manual_deposits WHERE status='pending' ORDER BY id DESC LIMIT 20")
 text='🧾 <b>MANUAL PAYMENTS</b>\n\n'+('\n'.join(f"#{r['id']} • {r['user_id']} • {r['amount']} • {r['status']}" for r in rows) if rows else 'Tidak ada pending.')
 buttons=[]
 for r in rows:
  buttons.append([
   InlineKeyboardButton(text=f'📎 Proof #{r["id"]}',callback_data=f'manproof:{r["id"]}'),
   InlineKeyboardButton(text='✅ Approve',callback_data=f'manapprove:{r["id"]}'),
   InlineKeyboardButton(text='❌ Reject',callback_data=f'manreject:{r["id"]}')
  ])
 buttons.append([InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')])
 await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith('manproof:'))
async def manproof(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 did=int(c.data.split(':',1)[1]); p=await get_pool()
 r=await p.fetchrow("SELECT * FROM manual_deposits WHERE id=$1",did)
 if not r or not r['proof_file_id']:
  return await c.answer('❌ Bukti belum dikirim.',show_alert=True)
 cap=(f'🧾 <b>MANUAL PAYMENT PROOF</b>\n\n'
      f'ID: <code>{did}</code>\nUser: <code>{r["user_id"]}</code>\n'
      f'Amount: <b>Rp{int(r["amount"]):,}</b>\nStatus: <b>{html.escape(str(r["status"]))}</b>').replace(',','.')
 kb=InlineKeyboardMarkup(inline_keyboard=[[
   InlineKeyboardButton(text='✅ Approve',callback_data=f'manapprove:{did}'),
   InlineKeyboardButton(text='❌ Reject',callback_data=f'manreject:{did}')
 ]])
 try:
  if r['proof_type']=='photo': await c.message.answer_photo(r['proof_file_id'],caption=cap,parse_mode='HTML',reply_markup=kb)
  else: await c.message.answer_document(r['proof_file_id'],caption=cap,parse_mode='HTML',reply_markup=kb)
  await c.answer()
 except Exception:
  await c.answer('❌ Gagal menampilkan bukti.',show_alert=True)

@router.callback_query(F.data=='adm:grantopen')
async def grantopen_start(c,state):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 await state.set_state(AdminState.grant_open_user)
 await c.message.answer('Kirim Telegram User ID yang akan diberi akses buka code.')

@router.message(AdminState.grant_open_user)
async def grantopen_user(m,state):
 if not await admin_access(m.from_user.id): return
 try: uid=int((m.text or '').strip())
 except: return await m.answer('User ID tidak valid.')
 p=await get_pool(); u=await p.fetchrow('SELECT user_id,username FROM users WHERE user_id=$1',uid)
 if not u:return await m.answer('User belum terdaftar di bot.')
 await state.update_data(grant_user=uid); await state.set_state(AdminState.grant_open_code); await m.answer('Sekarang kirim CODE yang ingin dibuka untuk user tersebut.')

@router.message(AdminState.grant_open_code)
async def grantopen_code(m,state):
 if not await admin_access(m.from_user.id): return
 d=await state.get_data(); uid=int(d.get('grant_user') or 0); code=(m.text or '').strip()
 p=await get_pool(); f=await p.fetchrow('SELECT owner_id,price_idr,active FROM files WHERE code=$1',code)
 if not f or not f['active']:
  return await m.answer('Code tidak ditemukan atau tidak aktif.')
 await p.execute("""INSERT INTO unlock_transactions(user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at)
    VALUES($1,$2,$3,'admin',$4,0,0,NOW()+INTERVAL '100 years')""",uid,f['owner_id'],code,f['price_idr'] or 0)
 await state.clear()
 from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
 try:
  await m.bot.send_message(uid,f'Admin memberikan akses buka code.\n\nCode: <code>{html.escape(code)}</code>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Buka Code',callback_data=f'getcode:{code}')]]))
  sent='Pesan dikirim ke user.'
 except Exception as exc:
  sent=f'Gagal mengirim pesan ke user: {html.escape(str(exc)[:120])}'
 await m.answer(f'Akses code diberikan untuk {uid}. {sent}')

@router.callback_query(F.data=='adm:roles')
async def roles_start(c,state):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 await state.set_state(AdminState.role_user); await c.message.answer('Kirim Telegram User ID yang akan diatur rolenya.')

@router.message(AdminState.role_user)
async def role_user(m,state):
 if not await admin_access(m.from_user.id): return
 try: uid=int((m.text or '').strip())
 except: return await m.answer('User ID tidak valid.')
 p=await get_pool(); u=await p.fetchrow('SELECT user_id,username,is_admin,is_creator,creator_status,vip FROM users WHERE user_id=$1',uid)
 if not u:return await m.answer('User tidak ditemukan.')
 await state.clear()
 rows=[[InlineKeyboardButton(text='Member',callback_data=f'admrole:member:{uid}'),InlineKeyboardButton(text='VIP',callback_data=f'admrole:vip:{uid}')],[InlineKeyboardButton(text='Creator',callback_data=f'admrole:creator:{uid}'),InlineKeyboardButton(text='Admin',callback_data=f'admrole:admin:{uid}')]]
 await m.answer(f'User <code>{uid}</code> @{html.escape(u["username"] or "-")}\n\nPilih role:',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('admrole:'))
async def role_apply(c):
 if not await admin_access(c.from_user.id): return await c.answer('No access',show_alert=True)
 _,role,uid_s=c.data.split(':',2); uid=int(uid_s); p=await get_pool()
 if role=='member':
  await p.execute("UPDATE users SET is_admin=FALSE,is_creator=FALSE,creator_status='none',vip=FALSE,vip_until=NULL WHERE user_id=$1",uid)
 elif role=='vip':
  await p.execute("UPDATE users SET is_admin=FALSE,is_creator=FALSE,creator_status='none',vip=TRUE,vip_until=NOW()+INTERVAL '30 days',vip_plan_days=30,vip_daily_limit=30 WHERE user_id=$1",uid)
 elif role=='creator':
  await p.execute("UPDATE users SET is_admin=FALSE,is_creator=TRUE,creator_status='approved',creator_previous=TRUE WHERE user_id=$1",uid)
 elif role=='admin':
  await p.execute("UPDATE users SET is_admin=TRUE WHERE user_id=$1",uid); ADMIN_IDS.add(uid)
 await c.answer(f'Role {role} diterapkan.')
 await c.message.edit_text(f'Role user <code>{uid}</code>: <b>{role.upper()}</b>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Kembali',callback_data='adm:panel')]]))

@router.callback_query(F.data.startswith('adm:users'))
async def users(c):
 if not await admin_access(c.from_user.id): return
 try: page=int(c.data.split(':')[2]) if len(c.data.split(':'))>2 else 0
 except: page=0
 off=page*15; rows=await (await get_pool()).fetch("SELECT user_id,username,balance,points,stars,vip,banned,is_creator FROM users ORDER BY last_seen DESC LIMIT 15 OFFSET $1",off)
 lines=[]
 for r in rows:
  plan='VIP' if r['vip'] else 'FREE'
  ban=' 🚫' if r['banned'] else ''
  lines.append(f"🆔 <code>{r['user_id']}</code> @{html.escape(r['username'] or '-')} • Rp{int(r['balance'] or 0):,} • {plan}{ban}")
 text=f'👥 <b>USERS</b> • Page {page+1}\n\n'+('\n'.join(lines).replace(',','.') if lines else 'Tidak ada user.')
 nav=[]
 if page>0:nav.append(InlineKeyboardButton(text='⬅️',callback_data=f'adm:users:{page-1}'))
 if len(rows)==15:nav.append(InlineKeyboardButton(text='➡️',callback_data=f'adm:users:{page+1}'))
 buttons=[nav] if nav else []
 buttons.append([InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')])
 await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith('adm:codes'))
async def codes(c):
    if not await admin_access(c.from_user.id):
        return await c.answer('No access', show_alert=True)
    try:
        page = int(c.data.split(':')[2]) if len(c.data.split(':')) > 2 else 0
    except Exception:
        page = 0
    page = max(0, page)
    p = await get_pool()
    rows = await p.fetch(
        """SELECT code,title,price_idr,views,likes,hates,favorites,active
           FROM files ORDER BY id DESC LIMIT 10 OFFSET $1""",
        page * 10,
    )
    lines = [f'🗂 <b>CODE MANAGEMENT</b> • Page {page+1}\n']
    if rows:
        for r in rows:
            price = int(r['price_idr'] or 0)
            price_txt = f'Rp{price:,}'.replace(',', '.') if price else 'FREE'
            status = '🟢' if r['active'] else '🔴'
            lines.append(
                f"{status} <code>{html.escape(r['code'])}</code> • "
                f"<b>{html.escape(r['title'] or '-')}</b>\n"
                f"💰 {price_txt} • 👁{r['views']} 👍{r['likes']} "
                f"👎{r['hates']} ⭐{r['favorites']}"
            )
    else:
        lines.append('Tidak ada code.')

    buttons = []
    for r in rows:
        title = (r['title'] or r['code'])[:32]
        buttons.append([
            InlineKeyboardButton(text=f'✏️ {title}', callback_data=f'admcode:edit:{r["code"]}'),
            InlineKeyboardButton(text='🗑 Hapus', callback_data=f'admcode:delete:{r["code"]}')
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='⬅️', callback_data=f'adm:codes:{page-1}'))
    if len(rows) == 10:
        nav.append(InlineKeyboardButton(text='➡️', callback_data=f'adm:codes:{page+1}'))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text='🔙 Panel', callback_data='adm:panel')])
    await c.message.edit_text(
        '\n'.join(lines),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith('admcode:edit:'))
async def admin_code_edit(c, state: FSMContext):
    if not await admin_access(c.from_user.id):
        return await c.answer('No access', show_alert=True)
    code = c.data.split(':', 2)[2]
    p = await get_pool()
    r = await p.fetchrow(
        "SELECT code,title,tags,price_idr,media_count FROM files WHERE code=$1",
        code,
    )
    if not r:
        return await c.answer('❌ Code tidak ditemukan.', show_alert=True)
    tags = r['tags'] or []
    price = int(r['price_idr'] or 0)
    price_txt = f'Rp{price:,}'.replace(',', '.') if price else 'FREE'
    text = (
        f"✏️ <b>EDIT CODE</b>\n\n"
        f"🔑 Code: <code>{html.escape(code)}</code>\n"
        f"📝 Judul: <b>{html.escape(r['title'] or '-')}</b>\n"
        f"🏷 Tag: <b>{html.escape(' '.join(tags) or '-')}</b>\n"
        f"💰 Harga: <b>{price_txt}</b>\n"
        f"📦 Media: <b>{r['media_count']}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📝 Edit Judul', callback_data=f'admcode:field:title:{code}')],
        [InlineKeyboardButton(text='🏷 Edit Tag', callback_data=f'admcode:field:tags:{code}')],
        [InlineKeyboardButton(text='💰 Edit Harga', callback_data=f'admcode:field:price:{code}')],
        [InlineKeyboardButton(text='🗑 Hapus Code', callback_data=f'admcode:delete:{code}')],
        [InlineKeyboardButton(text='🔙 Code', callback_data='adm:codes')],
    ])
    await c.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.startswith('admcode:field:'))
async def admin_code_field(c, state: FSMContext):
    if not await admin_access(c.from_user.id):
        return await c.answer('No access', show_alert=True)
    parts = c.data.split(':', 3)
    if len(parts) != 4:
        return await c.answer('Invalid request', show_alert=True)
    field, code = parts[2], parts[3]
    mapping = {
        'title': (AdminState.edit_title, '📝 Kirim judul baru untuk code ini.'),
        'tags': (AdminState.edit_tags, '🏷 Kirim tag baru, pisahkan dengan spasi.'),
        'price': (AdminState.edit_price, f'💰 Kirim harga baru (Rp{PAID_CODE_MIN_IDR:,} - Rp{PAID_CODE_MAX_IDR:,}).'.replace(',', '.')),
    }
    if field not in mapping:
        return await c.answer('Field tidak dikenal.', show_alert=True)
    await state.set_state(mapping[field][0])
    await state.update_data(code=code)
    await c.message.answer(mapping[field][1])
    await c.answer()


@router.message(AdminState.edit_title)
async def admin_edit_title(m, state: FSMContext):
    d = await state.get_data()
    code = d.get('code')
    title = (m.text or '').strip()
    if not code:
        await state.clear()
        return await m.answer('❌ Sesi edit sudah berakhir.')
    if not title:
        return await m.answer('❌ Judul tidak boleh kosong.')
    await (await get_pool()).execute(
        "UPDATE files SET title=$1 WHERE code=$2", title[:150], code
    )
    await state.clear()
    await m.answer('✅ Judul code berhasil diperbarui.')
    await m.answer(await panel_text(), parse_mode='HTML', reply_markup=kb())


@router.message(AdminState.edit_tags)
async def admin_edit_tags(m, state: FSMContext):
    d = await state.get_data()
    code = d.get('code')
    raw = (m.text or '').strip()
    if not code:
        await state.clear()
        return await m.answer('❌ Sesi edit sudah berakhir.')
    tags = [x[:30] for x in raw.split()[:10]] if raw else []
    await (await get_pool()).execute(
        "UPDATE files SET tags=$1::text[] WHERE code=$2", tags, code
    )
    await state.clear()
    await m.answer('✅ Tag code berhasil diperbarui.')


@router.message(AdminState.edit_price)
async def admin_edit_price(m, state: FSMContext):
    d = await state.get_data()
    code = d.get('code')
    if not code:
        await state.clear()
        return await m.answer('❌ Sesi edit sudah berakhir.')
    raw = re.sub(r'\D', '', m.text or '')
    if not raw:
        return await m.answer('❌ Kirim angka harga.')
    price = int(raw)
    if price and not (PAID_CODE_MIN_IDR <= price <= PAID_CODE_MAX_IDR):
        return await m.answer(
            f'❌ Harga harus Rp{PAID_CODE_MIN_IDR:,} s/d Rp{PAID_CODE_MAX_IDR:,}.'.replace(',', '.')
        )
    await (await get_pool()).execute(
        "UPDATE files SET price_idr=$1,code_value_idr=$1 WHERE code=$2",
        price, code
    )
    await state.clear()
    await m.answer('✅ Harga code berhasil diperbarui.')


@router.callback_query(F.data.startswith('admcode:delete:'))
async def admin_code_delete_confirm(c):
    if not await admin_access(c.from_user.id):
        return await c.answer('No access', show_alert=True)
    code = c.data.split(':', 2)[2]
    p = await get_pool()
    r = await p.fetchrow(
        "SELECT code,title,media_count FROM files WHERE code=$1",
        code,
    )
    if not r:
        return await c.answer('❌ Code tidak ditemukan.', show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⚠️ Ya, Hapus Permanen', callback_data=f'admcode:deleteyes:{code}')],
        [InlineKeyboardButton(text='❌ Batal', callback_data=f'admcode:edit:{code}')],
    ])
    await c.message.edit_text(
        f"⚠️ <b>HAPUS CODE PERMANEN?</b>\n\n"
        f"🔑 <code>{html.escape(code)}</code>\n"
        f"📝 {html.escape(r['title'] or '-')}\n"
        f"📦 {r['media_count']} media\n\n"
        f"Semua object media yang tercatat di Backblaze B2 juga akan dihapus.",
        parse_mode='HTML',
        reply_markup=kb
    )
    await c.answer()


@router.callback_query(F.data.startswith('admcode:deleteyes:'))
async def admin_code_delete(c):
    if not await admin_access(c.from_user.id):
        return await c.answer('No access', show_alert=True)
    code = c.data.split(':', 2)[2]
    p = await get_pool()
    r = await p.fetchrow("SELECT code,title,media FROM files WHERE code=$1", code)
    if not r:
        return await c.answer('❌ Code sudah tidak ada.', show_alert=True)

    try:
        media = r['media'] if isinstance(r['media'], list) else __import__('json').loads(r['media'] or '[]')
    except Exception:
        media = []

    deleted_b2 = 0
    failed_b2 = 0
    for item in media:
        try:
            account_id = int(item.get('drive_account') or 0)
            object_key = str(item.get('drive_file_id') or '')
            if account_id and object_key:
                if await b2_pool.delete(account_id, object_key):
                    deleted_b2 += 1
                else:
                    failed_b2 += 1
        except Exception:
            failed_b2 += 1

    if failed_b2:
        # Do not remove the DB record when some storage objects could not be deleted.
        return await c.message.edit_text(
            f"❌ <b>Code belum dihapus.</b>\n\n"
            f"🔑 <code>{html.escape(code)}</code>\n"
            f"🗑 B2 terhapus: {deleted_b2}\n"
            f"⚠️ B2 gagal: {failed_b2}\n\n"
            f"Periksa B2 lalu coba hapus lagi agar tidak meninggalkan object yatim.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔄 Coba Lagi', callback_data=f'admcode:delete:{code}')],
                [InlineKeyboardButton(text='🔙 Code', callback_data='adm:codes')]
            ])
        )

    # Clean non-FK code metadata explicitly, then hard-delete the code.
    await p.execute("DELETE FROM code_group_shares WHERE code=$1", code)
    await p.execute("DELETE FROM code_cooldowns WHERE code=$1", code)
    await p.execute("DELETE FROM files WHERE code=$1", code)

    await c.message.edit_text(
        f"✅ <b>CODE DIHAPUS PERMANEN</b>\n\n"
        f"🔑 <code>{html.escape(code)}</code>\n"
        f"🗑 Backblaze B2: <b>{deleted_b2}</b> object terhapus.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🗂 Code', callback_data='adm:codes')],
            [InlineKeyboardButton(text='🔙 Panel', callback_data='adm:panel')]
        ])
    )
    await c.answer('Code dan media B2 berhasil dihapus.')


@router.callback_query(F.data=='adm:broadcast')
async def broadcast_start(c,state):
 if not await admin_access(c.from_user.id): return
 await state.set_state(AdminState.broadcast); await c.message.answer('📢 Kirim pesan broadcast.')

@router.message(AdminState.broadcast)
async def broadcast(m,state):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 users=await (await get_pool()).fetch("SELECT user_id FROM users WHERE NOT banned")
 ok=0
 for r in users:
  try: await m.bot.copy_message(r['user_id'],m.chat.id,m.message_id); ok+=1
  except: pass
 await state.clear(); await m.answer(f'✅ Broadcast selesai: {ok}/{len(users)}')

@router.message(Command('editcode'))
async def editcode(m,state):
 if not await admin_access(m.from_user.id):return
 code=(m.text or '').split(maxsplit=1)[1] if len((m.text or '').split(maxsplit=1))>1 else ''
 if not code:return await m.answer('Format: /editcode CODE')
 r=await (await get_pool()).fetchrow("SELECT title,tags,price_idr FROM files WHERE code=$1",code)
 if not r:return await m.answer('❌ Code tidak ditemukan.')
 await state.set_state(AdminState.edit_title); await state.update_data(code=code)
 await m.answer(f"📝 Judul sekarang: {r['title'] or '-'}\nKirim judul baru.")

@router.message(Command('deletecode'))
async def deletecode(m):
 if not await admin_access(m.from_user.id):return
 parts=(m.text or '').split(maxsplit=1)
 if len(parts)<2:return await m.answer('/deletecode CODE')
 r=await (await get_pool()).fetchrow("UPDATE files SET active=FALSE WHERE code=$1 RETURNING code",parts[1].strip())
 await m.answer('✅ Code dinonaktifkan.' if r else '❌ Tidak ditemukan.')

@router.message(Command('broadcast'))
async def broadcast_cmd(m,state):
 if not await admin_access(m.from_user.id):return
 await state.set_state(AdminState.broadcast); await m.answer('📢 Kirim pesan yang akan dibroadcast.')

@router.message(Command('grantcreator'))
async def grantcreator(m):
 if not await admin_access(m.from_user.id):return
 parts=(m.text or '').split()
 if len(parts)!=2:return await m.answer('/grantcreator USER_ID')
 r=await (await get_pool()).fetchrow("UPDATE users SET is_creator=TRUE,creator_status='approved' WHERE user_id=$1 RETURNING user_id",int(parts[1]))
 await m.answer('✅ Creator aktif.' if r else '❌ User tidak ditemukan.')

@router.message(Command('user'))
async def user_action(m):
 if not await admin_access(m.from_user.id):return
 parts=(m.text or '').split()
 if len(parts)<3:return await m.answer('/user USER_ID vip|creator|admin|ban|unban|unlock')
 uid=int(parts[1]); action=parts[2].lower(); p=await get_pool()
 if action=='vip': await p.execute("UPDATE users SET vip=TRUE,vip_until=NOW()+INTERVAL '30 days',vip_plan_days=30,vip_daily_limit=30 WHERE user_id=$1",uid)
 elif action=='creator': await p.execute("UPDATE users SET is_creator=TRUE,creator_status='approved' WHERE user_id=$1",uid)
 elif action=='admin':
  await p.execute("UPDATE users SET is_admin=TRUE WHERE user_id=$1",uid)
  ADMIN_IDS.add(uid)
 elif action=='ban': await p.execute("UPDATE users SET banned=TRUE WHERE user_id=$1",uid)
 elif action=='unban': await p.execute("UPDATE users SET banned=FALSE WHERE user_id=$1",uid)
 elif action=='unlock': await p.execute("UPDATE users SET can_unlock=TRUE WHERE user_id=$1",uid)
 elif action=='lock': await p.execute("UPDATE users SET can_unlock=FALSE WHERE user_id=$1",uid)
 else:return await m.answer('❌ Action tidak dikenal.')
 await m.answer(f'✅ {action} → {uid}')

@router.message(Command('setcodeprice'))
async def setcodeprice(m):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 parts=(m.text or '').split()
 if len(parts)!=3:return await m.answer('/setcodeprice CODE PRICE')
 price=int(re.sub(r'\D','',parts[2]))
 if price and not (PAID_CODE_MIN_IDR<=price<=PAID_CODE_MAX_IDR): return await m.answer('Harga di luar batas.')
 r=await (await get_pool()).fetchrow("UPDATE files SET price_idr=$1 WHERE code=$2 RETURNING code",price,parts[1])
 await m.answer('✅ Harga diperbarui.' if r else '❌ Code tidak ditemukan.')

@router.message(Command('setcodetags'))
async def setcodetags(m):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 parts=(m.text or '').split(maxsplit=2)
 if len(parts)!=3:return await m.answer('/setcodetags CODE tag1 tag2 tag3')
 tags=[x[:30] for x in parts[2].split()[:10]]
 r=await (await get_pool()).fetchrow("UPDATE files SET tags=$1 WHERE code=$2 RETURNING code",tags,parts[1])
 await m.answer('✅ Tag diperbarui.' if r else '❌ Code tidak ditemukan.')

@router.callback_query(F.data=='adm:errors')
async def errors(c):
 if not await admin_access(c.from_user.id): return
 rows=await (await get_pool()).fetch("SELECT source,message,created_at FROM error_logs ORDER BY id DESC LIMIT 20")
 text='🚨 <b>BOT ERRORS</b>\n\n'+('\n'.join(f"• {r['created_at']:%d-%m %H:%M} [{html.escape(r['source'] or '-')}] {html.escape(r['message'][:180])}" for r in rows) if rows else 'Tidak ada error.')
 await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]]))

@router.message(AdminState.user_action)
async def save_setting(m,state):
 if not await admin_access(m.from_user.id): return await m.answer(f'❌ Tidak ada akses admin.\n🆔 <code>{m.from_user.id}</code>',parse_mode='HTML')
 d=await state.get_data()
 key=d.get('setting')
 if not key:return
 try: value=int(re.sub(r'\D','',m.text or ''))
 except:return await m.answer('❌ Angka tidak valid.')
 await setval(key,value); await state.clear(); await m.answer(f'✅ {key} = {value}')
