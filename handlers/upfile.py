
from __future__ import annotations
import asyncio,json,os,secrets,tempfile,html,re
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import MAX_MEDIA,BOT_USERNAME,PAID_CODE_MIN_IDR,PAID_CODE_MAX_IDR,MAX_MEDIA_SIZE_MB,MAX_MEDIA_SIZE_BYTES,TELEGRAM_API_BASE
from utils.b2_storage import b2_pool
from utils.callback_loading import loading
from utils.economy import is_creator
router=Router()
_LOCKS={}
class U(StatesGroup):
    media=State(); title=State(); tags=State(); price=State()

def rnd(n=11): return ''.join(secrets.choice('123456789XxYy') for _ in range(n))
async def new_code(counts):
    p=await get_pool()
    while True:
        code=f"{BOT_USERNAME}_{rnd()}_{counts[0]}p{counts[1]}v{counts[2]}d"
        if not await p.fetchval('SELECT 1 FROM files WHERE code=$1',code): return code

def media_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Selesai Upload',callback_data='up_finish')],
        [InlineKeyboardButton(text='❌ Batal',callback_data='up_cancel')]])

def clean_tags(s):
    parts=[re.sub(r'[,\n#]+',' ',x).strip() for x in (s or '').split()]
    return [x[:30] for x in parts if x][:10]

@router.callback_query(F.data=='upfile')
async def start(c,state):
    await loading(c); await state.clear(); await state.set_state(U.media)
    await state.update_data(media=[],status_message_id=None)
    msg=await c.message.answer(
        f'📤 <b>UP FILE</b>\n\nKirim maksimal <b>{MAX_MEDIA}</b> media.\n'
        'Setiap media diproses ke Backblaze B2. Setelah selesai tekan <b>✅ Selesai Upload</b>.',
        parse_mode='HTML',reply_markup=media_kb())
    await state.update_data(status_message_id=msg.message_id)

@router.message(F.chat.type == "private", U.media)
async def receive(m,state):
    uid=m.from_user.id
    lock=_LOCKS.setdefault(uid,asyncio.Lock())
    async with lock:
        d=await state.get_data(); media=list(d.get('media',[])); status_id=d.get('status_message_id')
        if len(media)>=MAX_MEDIA:
            try: await m.delete()
            except: pass
            return
        typ=fid=name=mime=None; size=0
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
            except: pass
            return
        if not b2_pool.available:
            try: await m.delete()
            except: pass
            if status_id:
                try: await m.bot.edit_message_text(chat_id=m.chat.id,message_id=status_id,text='❌ <b>B2 belum siap.</b>',parse_mode='HTML',reply_markup=media_kb())
                except: pass
            return
        fd,path=tempfile.mkstemp(prefix='pastele_'); os.close(fd)
        try:
            # Application limit: 100 MB by default.
            # Files above ~20 MB require a Local Bot API Server because the
            # standard Telegram cloud Bot API cannot download them with getFile.
            if size and size > MAX_MEDIA_SIZE_BYTES:
                msg = (
                    '❌ <b>Media terlalu besar.</b>\n\n'
                    f'📦 Ukuran: <b>{size / 1024 / 1024:.1f} MB</b>\n'
                    f'📏 Maksimal: <b>{MAX_MEDIA_SIZE_MB} MB</b> per media.\n\n'
                    'Silakan kirim media yang ukurannya lebih kecil.'
                )
                if status_id:
                    try:
                        await m.bot.edit_message_text(chat_id=m.chat.id, message_id=status_id, text=msg, parse_mode='HTML', reply_markup=media_kb())
                    except Exception:
                        await m.answer(msg, parse_mode='HTML', reply_markup=media_kb())
                else:
                    await m.answer(msg, parse_mode='HTML', reply_markup=media_kb())
                try: await m.delete()
                except: pass
                return

            if size and size > 20 * 1024 * 1024 and not TELEGRAM_API_BASE:
                msg = (
                    '❌ <b>Media lebih dari 20 MB belum bisa di-download bot.</b>\n\n'
                    f'📦 Ukuran: <b>{size / 1024 / 1024:.1f} MB</b>\n'
                    f'📏 Batas aplikasi: <b>{MAX_MEDIA_SIZE_MB} MB</b>.\n\n'
                    'Untuk menerima media 21–100 MB, aktifkan <b>Local Bot API Server</b> '
                    'dan isi environment variable <code>TELEGRAM_API_BASE</code>.'
                )
                if status_id:
                    try:
                        await m.bot.edit_message_text(chat_id=m.chat.id, message_id=status_id, text=msg, parse_mode='HTML', reply_markup=media_kb())
                    except Exception:
                        await m.answer(msg, parse_mode='HTML', reply_markup=media_kb())
                else:
                    await m.answer(msg, parse_mode='HTML', reply_markup=media_kb())
                try: await m.delete()
                except: pass
                return
            if status_id:
                try: await m.bot.edit_message_text(chat_id=m.chat.id,message_id=status_id,text=f'⏳ <b>Loading…</b>\n\n📤 Menyimpan media <b>{len(media)+1}/{MAX_MEDIA}</b>',parse_mode='HTML',reply_markup=media_kb())
                except: pass
            f=await m.bot.get_file(fid); await m.bot.download_file(f.file_path,path)
            account,key,_=await b2_pool.upload(path,name,mime)
            media.append({'telegram_file_id':fid,'telegram_file_unique_id':getattr((m.photo[-1] if m.photo else m.video if m.video else m.document if m.document else m.audio),'file_unique_id',None),'drive_account':account,'drive_file_id':key,'type':typ,'file_name':name,'file_size':size,'mime_type':mime,'storage_status':'b2_available'})
            await state.update_data(media=media)
            if status_id:
                try: await m.bot.edit_message_text(chat_id=m.chat.id,message_id=status_id,text=f'📤 <b>UP FILE</b>\n\n✅ <b>{len(media)}/{MAX_MEDIA}</b> media tersimpan.\n\nTekan <b>✅ Selesai Upload</b> untuk lanjut.',parse_mode='HTML',reply_markup=media_kb())
                except: pass
            try: await m.delete()
            except: pass
        except Exception as exc:
            try: await m.delete()
            except: pass
            try:
                await (await get_pool()).execute("INSERT INTO error_logs(source,message,user_id) VALUES($1,$2,$3)",'upfile',str(exc)[:1000],uid)
            except: pass
            try:
                from utils.notify_channel import notify
                await notify(m.bot, f'🚨 <b>BOT ERROR — UP FILE</b>\n\n🆔 User: <code>{uid}</code>\n❌ <code>{str(exc)[:900]}</code>')
            except: pass
            if status_id:
                try: await m.bot.edit_message_text(chat_id=m.chat.id,message_id=status_id,text=f'❌ <b>Gagal menyimpan media.</b>\n\n📦 Tersimpan: <b>{len(media)}/{MAX_MEDIA}</b>',parse_mode='HTML',reply_markup=media_kb())
                except: pass
        finally:
            try: os.remove(path)
            except: pass

@router.callback_query(F.data=='up_finish')
async def finish(c,state):
    d=await state.get_data(); media=d.get('media',[])
    if not media:return await c.answer('Belum ada media.',show_alert=True)
    await state.set_state(U.title)
    await c.message.edit_text(f'📝 <b>MASUKKAN JUDUL</b>\n\n📦 {len(media)} media siap disimpan.\n\nKirim judul code:',parse_mode='HTML')

@router.message(U.title)
async def title(m,state):
    title=(m.text or '').strip()
    if not title:return await m.answer('❌ Judul tidak boleh kosong.')
    await state.update_data(title=title[:150]); await state.set_state(U.tags)
    await m.answer('🏷 <b>MASUKKAN TAG</b>\n\nContoh: <code>movie action 2026</code>\nKirim maksimal 10 tag. Jika tidak ada, kirim <code>-</code>.',parse_mode='HTML')

@router.message(U.tags)
async def tags(m,state):
    raw=(m.text or '').strip()
    tags=[] if raw=='-' else clean_tags(raw)
    await state.update_data(tags=tags); await state.set_state(U.price)
    creator=await is_creator(m.from_user.id)
    from config import OWNER_ID,ADMIN_IDS
    paid_allowed=creator or m.from_user.id==OWNER_ID or m.from_user.id in ADMIN_IDS
    text='💰 <b>MASUKKAN HARGA CODE</b>\n\n'
    if paid_allowed:
        text+=f'Creator/Admin dapat membuat paid code.\nMinimal Rp{PAID_CODE_MIN_IDR:,} • Maksimal Rp{PAID_CODE_MAX_IDR:,} • kelipatan Rp1.000\nKirim <code>0</code> untuk FREE.'.replace(',','.')
    else:text+='Akun kamu hanya dapat membuat FREE code.\nKirim <code>0</code>.'
    await m.answer(text,parse_mode='HTML')

@router.message(U.price)
async def price(m,state):
    d=await state.get_data()
    try: price=int(re.sub(r'\D','',m.text or ''))
    except: price=-1
    creator=await is_creator(m.from_user.id)
    from config import OWNER_ID,ADMIN_IDS
    allowed=creator or m.from_user.id==OWNER_ID or m.from_user.id in ADMIN_IDS
    if price<0:return await m.answer('❌ Harga tidak valid.')
    if not allowed and price!=0:return await m.answer('❌ Hanya Creator/Admin yang dapat membuat paid code. Kirim 0.')
    if allowed and creator and price==0:
        p=await get_pool()
        already=await p.fetchval("SELECT 1 FROM files WHERE owner_id=$1 AND price_idr>0 AND created_at::date=CURRENT_DATE LIMIT 1",m.from_user.id)
        if not already:
            return await m.answer('Creator wajib membuat minimal 1 Paid Code setiap hari. Masukkan harga mulai Rp2.000.')
    if allowed and price and not (PAID_CODE_MIN_IDR<=price<=PAID_CODE_MAX_IDR):
        return await m.answer(f'❌ Harga harus Rp{PAID_CODE_MIN_IDR:,} s/d Rp{PAID_CODE_MAX_IDR:,}.'.replace(',','.'))
    media=d.get('media',[]); title=d.get('title','Untitled'); tags=d.get('tags',[])
    counts=[sum(x['type']=='photo' for x in media),sum(x['type']=='video' for x in media),sum(x['type']=='document' for x in media)]
    code=await new_code(counts); p=await get_pool()
    value=len(media)*100
    await p.execute("""INSERT INTO files(code,owner_id,title,media,media_count,photo_count,video_count,document_count,audio_count,code_value_idr,tags,price_idr)
    VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10,$11,$12)""",
    code,m.from_user.id,title,json.dumps(media),len(media),counts[0],counts[1],counts[2],sum(x['type']=='audio' for x in media),value,tags,price)
    await state.clear()
    tagtext=' '.join('#'+html.escape(t) for t in tags) or '-'
    paytxt=f'💰 Rp{price:,}'.replace(',','.') if price else '🆓 FREE'
    await m.answer(
        f'✅ <b>CODE BERHASIL DIBUAT</b>\n\n📝 Judul: <b>{html.escape(title)}</b>\n🏷 Tag: {tagtext}\n💰 Harga: <b>{paytxt}</b>\n🔑 <code>{code}</code>\n📦 {len(media)} media',
        parse_mode='HTML')

@router.callback_query(F.data=='up_cancel')
async def cancel(c,state):
    await loading(c); await state.clear(); await c.message.edit_text('❌ Upload dibatalkan.')
