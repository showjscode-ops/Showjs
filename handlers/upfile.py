from __future__ import annotations
import json,os,re,secrets,string,tempfile,html
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import MAX_MEDIA,BOT_USERNAME
from utils.b2_storage import b2_pool
from utils.callback_loading import loading
router=Router()
class U(StatesGroup): media=State(); price=State()
def rnd(n=11): return ''.join(secrets.choice('123456789XxYy') for _ in range(n))
async def new_code(counts):
 p=await get_pool()
 while True:
  code=f"{BOT_USERNAME}_{rnd()}_{counts[0]}p{counts[1]}v{counts[2]}d"
  if not await p.fetchval('SELECT 1 FROM files WHERE code=$1',code):return code
def kb():return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💾 Simpan & Buat Code',callback_data='up_save')],[InlineKeyboardButton(text='❌ Batal',callback_data='up_cancel')]])
@router.callback_query(F.data=='upfile')
async def start(c,state):
 await loading(c)
 await state.clear()
 await state.set_state(U.media)
 await state.update_data(media=[], status_message_id=None)
 msg = await c.message.answer(
     f'📤 <b>UP FILE</b>\n\nKirim maksimal <b>{MAX_MEDIA}</b> media. Semua media otomatis masuk Backblaze B2. Setelah selesai tekan Simpan.',
     parse_mode='HTML', reply_markup=kb())
 await state.update_data(status_message_id=msg.message_id)
@router.message(U.media)
async def receive(m,state):
 d=await state.get_data()
 media=list(d.get('media',[]))
 title=(d.get('title') or '').strip()
 status_id=d.get('status_message_id')
 if len(media)>=MAX_MEDIA:
  try: await m.delete()
  except Exception: pass
  if status_id:
   try:
    await m.bot.edit_message_text(
        chat_id=m.chat.id, message_id=status_id,
        text=f'📤 <b>UP FILE</b>\n\n⚠️ Maksimal <b>{MAX_MEDIA}</b> media sudah tercapai.\n\nTekan <b>Simpan & Buat Code</b> untuk menyelesaikan.',
        parse_mode='HTML', reply_markup=kb())
   except Exception: pass
  return
 typ=fid=name=mime=None
 size=0
 if m.photo:
  p=m.photo[-1]; typ='photo'; fid=p.file_id; name=f'{p.file_unique_id}.jpg'; mime='image/jpeg'; size=p.file_size or 0
 elif m.video:
  typ='video'; fid=m.video.file_id; name=m.video.file_name or f'{m.video.file_unique_id}.mp4'; mime=m.video.mime_type or 'video/mp4'; size=m.video.file_size or 0
 elif m.document:
  typ='document'; fid=m.document.file_id; name=m.document.file_name or m.document.file_unique_id; mime=m.document.mime_type or 'application/octet-stream'; size=m.document.file_size or 0
 elif m.audio:
  typ='audio'; fid=m.audio.file_id; name=m.audio.file_name or f'{m.audio.file_unique_id}.mp3'; mime=m.audio.mime_type or 'audio/mpeg'; size=m.audio.file_size or 0
 else:
  try: await m.delete()
  except Exception: pass
  return
 if not b2_pool.available:
  try: await m.delete()
  except Exception: pass
  if status_id:
   try:
    await m.bot.edit_message_text(chat_id=m.chat.id, message_id=status_id,
        text='⚠️ <b>Backblaze B2 belum dikonfigurasi.</b>', parse_mode='HTML', reply_markup=kb())
   except Exception: pass
  return
 fd,path=tempfile.mkstemp(prefix='pastele_'); os.close(fd)
 try:
  # Keep the user-facing progress as ONE message: upload starts -> progress -> done.
  if status_id:
   try:
    await m.bot.edit_message_text(
        chat_id=m.chat.id, message_id=status_id,
        text=f'⏳ <b>Loading…</b>\n\n📤 Menyimpan media <b>{len(media)+1}/{MAX_MEDIA}</b>…',
        parse_mode='HTML', reply_markup=kb())
   except Exception: pass
  f=await m.bot.get_file(fid)
  await m.bot.download_file(f.file_path,path)
  account,b2_key,_=await b2_pool.upload(path,name,mime)
  media.append({'drive_account':account,'drive_file_id':b2_key,'type':typ,'file_name':name,'file_size':size,'mime_type':mime})
  title = title or (m.caption or '').strip()
  await state.update_data(media=media,title=title)
  if status_id:
   try:
    await m.bot.edit_message_text(
        chat_id=m.chat.id, message_id=status_id,
        text=f'📤 <b>UP FILE</b>\n\n✅ <b>{len(media)}/{MAX_MEDIA}</b> media tersimpan.\n\nTekan <b>Simpan & Buat Code</b> jika sudah selesai.',
        parse_mode='HTML', reply_markup=kb())
   except Exception: pass
  try: await m.delete()
  except Exception: pass
 except Exception:
  try: await m.delete()
  except Exception: pass
  if status_id:
   try:
    await m.bot.edit_message_text(chat_id=m.chat.id, message_id=status_id,
        text=f'❌ <b>Gagal menyimpan media.</b>\n\n📦 Tersimpan: <b>{len(media)}/{MAX_MEDIA}</b>',
        parse_mode='HTML', reply_markup=kb())
   except Exception: pass
 finally:
  try: os.remove(path)
  except Exception: pass
@router.callback_query(F.data=='up_cancel')
async def cancel(c,state):
 await loading(c); await state.clear(); await c.message.edit_text('❌ Upload dibatalkan.')
@router.callback_query(F.data=='up_save')
async def save(c,state):
 d=await state.get_data(); media=d.get('media',[])
 if not media:return await c.answer('Belum ada media.',show_alert=True)
 counts=[sum(x['type']=='photo' for x in media),sum(x['type']=='video' for x in media),sum(x['type']=='document' for x in media)]
 code=await new_code(counts); value=len(media)*100
 title=(d.get('title') or '').strip() or f'{len(media)} Media'
 p=await get_pool()
 await p.execute("INSERT INTO files(code,owner_id,title,media,media_count,photo_count,video_count,document_count,audio_count,code_value_idr) VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10)",code,c.from_user.id,title,json.dumps(media),len(media),counts[0],counts[1],counts[2],sum(x['type']=='audio' for x in media),value)
 await state.clear()
 await loading(c)
 await c.message.edit_text(
     f'✅ <b>CODE BERHASIL DIBUAT</b>\n\n📝 Judul: <b>{title}</b>\n🔑 <code>{code}</code>\n📦 {counts[0]}p{counts[1]}v{counts[2]}d\n🪙 Unlock: {len(media)} Poin\n⭐ Unlock: {len(media)*0.02:g} Star',
     parse_mode='HTML'
 )
 # Automatically publish the saved code to the configured code group.
 from config import CODE_GROUP_ID, BOT_USERNAME
 if CODE_GROUP_ID:
  from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
  try:
   text=(f'💾 <b>MEDIA SAVE</b>\n\n📝 Judul: <b>{html.escape(title)}</b>\n🔑 Code: <code>{code}</code>\n🤖 Bot: @{BOT_USERNAME}')
   kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📥 Get File',callback_data=f'getcode:{code}')]])
   await c.bot.send_message(CODE_GROUP_ID,text,parse_mode='HTML',reply_markup=kb)
   await p.execute("INSERT INTO code_group_shares(code,group_id,shared_by) VALUES($1,$2,$3) ON CONFLICT(code,group_id) DO UPDATE SET last_seen_at=NOW()",code,CODE_GROUP_ID,c.from_user.id)
  except Exception:
   pass
