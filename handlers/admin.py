
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
    creator=State(); broadcast=State(); edit_code=State(); edit_title=State(); edit_tags=State(); edit_price=State(); user_action=State(); move=State()

def admin(uid): return is_config_admin(uid)
async def val(key): return str(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key=$1",key) or "off")
async def setval(key,value): await (await get_pool()).execute("INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",key,str(value))

def kb():
 return InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text='💳 Pembayaran',callback_data='adm:payments'),InlineKeyboardButton(text='📢 Broadcast',callback_data='adm:broadcast')],
  [InlineKeyboardButton(text='🗂 Code',callback_data='adm:codes'),InlineKeyboardButton(text='👥 Users',callback_data='adm:users')],
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
 rows=[]
 preferred=int(await (await get_pool()).fetchval("SELECT value FROM settings WHERE key='preferred_b2_account'") or 0)
 for a in b2_pool.accounts:
  star=' ⭐' if preferred==a.account_id else ''
  rows.append([InlineKeyboardButton(text=f'🗄 B2 #{a.account_id} {a.bucket}{star}',callback_data=f'b2select:{a.account_id}')])
 rows += [[InlineKeyboardButton(text='🩺 Cek Semua',callback_data='b2health')],[InlineKeyboardButton(text='📦 Kapasitas',callback_data='b2stats')],[InlineKeyboardButton(text='🔄 AUTO / FAILOVER',callback_data='b2auto')],[InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]]
 await c.message.edit_text(f'🗄 <b>B2 STORAGE</b>\\n\\nConfigured: {len(b2_pool.accounts)}/10',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith('b2select:'))
async def b2select(c):
 if not await admin_access(c.from_user.id): return
 aid=int(c.data.split(':')[1]); await setval('preferred_b2_account',aid); await c.answer(f'B2 #{aid} menjadi target upload.'); await b2menu(c)

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
 await c.message.edit_text('\\n'.join(lines),parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 B2',callback_data='adm:b2')]]))

@router.callback_query(F.data=='b2stats')
async def b2stats(c):
 if not await admin_access(c.from_user.id): return
 lines=['📦 <b>B2 CAPACITY</b>']
 for a in b2_pool.accounts:
  try:
   s=await b2_pool.stats(a.account_id); gb=s['bytes']/1024**3
   lines.append(f"🗄 B2 #{a.account_id}: {s['objects']} objects • {gb:.2f} GB")
  except Exception as e: lines.append(f"🔴 B2 #{a.account_id}: {str(e)[:80]}")
 await c.message.edit_text('\\n'.join(lines),parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 B2',callback_data='adm:b2')]]))

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
 text='🧾 <b>MANUAL PAYMENTS</b>\\n\\n'+('\\n'.join(f"#{r['id']} • {r['user_id']} • {r['amount']} • {r['status']}" for r in rows) if rows else 'Tidak ada pending.')
 buttons=[[InlineKeyboardButton(text=f'✅ #{r["id"]} Approve',callback_data=f'manapprove:{r["id"]}'),InlineKeyboardButton(text='❌ Reject',callback_data=f'manreject:{r["id"]}')] for r in rows]
 buttons.append([InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')])
 await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

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

@router.callback_query(F.data=='adm:codes')
async def codes(c):
 if not await admin_access(c.from_user.id): return
 rows=await (await get_pool()).fetch("SELECT code,title,price_idr,views,likes,hates,favorites FROM files ORDER BY id DESC LIMIT 15")
 text='🗂 <b>CODES</b>\\n\\n'+('\\n'.join(f"<code>{r['code']}</code> • {html.escape(r['title'] or '-') } • Rp{int(r['price_idr'] or 0):,} • 👁{r['views']} 👍{r['likes']} 👎{r['hates']} ⭐{r['favorites']}" for r in rows).replace(',','.') if rows else 'Kosong')
 await c.message.edit_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Panel',callback_data='adm:panel')]]))

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
 await m.answer(f"📝 Judul sekarang: {r['title'] or '-'}\\nKirim judul baru.")

@router.message(AdminState.edit_title)
async def edit_title(m,state):
 d=await state.get_data(); await (await get_pool()).execute("UPDATE files SET title=$1 WHERE code=$2",m.text[:150],d['code'])
 await state.clear(); await m.answer('✅ Judul code diperbarui.')

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
 if action=='vip': await p.execute("UPDATE users SET vip=TRUE,vip_until=NOW()+INTERVAL '30 days' WHERE user_id=$1",uid)
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
