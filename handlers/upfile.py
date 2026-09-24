
from __future__ import annotations
import asyncio,json,os,secrets,tempfile,html,re
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from database import get_pool
from config import MAX_MEDIA,BOT_USERNAME,PAID_CODE_MIN_IDR,PAID_CODE_MAX_IDR
from utils.b2_storage import b2_pool
from utils.callback_loading import loading
from utils.i18n import get_lang, translate
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
        'Media sampai 20 MB disimpan ke Backblaze B2. Media di atas 20 MB otomatis memakai Telegram file_id. Setelah selesai tekan <b>✅ Selesai Upload</b>.',
        parse_mode='HTML',reply_markup=media_kb())
    await state.update_data(status_message_id=msg.message_id)

@router.message(F.chat.type == "private", U.media)
async def receive(m,state):
    uid=m.from_user.id
    lock=_LOCKS.setdefault(uid,asyncio.Lock())
    async with lock:
        d=await state.get_data()
        media=list(d.get('media',[]))
        status_id=d.get('status_message_id')
        path=None

        if len(media)>=MAX_MEDIA:
            try: await m.delete()
            except: pass
            return

        typ=fid=name=mime=None
        size=0
        obj=None
        if m.photo:
            obj=m.photo[-1]
            typ='photo'; fid=obj.file_id; name=f'{obj.file_unique_id}.jpg'; mime='image/jpeg'; size=obj.file_size or 0
        elif m.video:
            obj=m.video
            typ='video'; fid=obj.file_id; name=obj.file_name or f'{obj.file_unique_id}.mp4'; mime=obj.mime_type or 'video/mp4'; size=obj.file_size or 0
        elif m.document:
            obj=m.document
            typ='document'; fid=obj.file_id; name=obj.file_name or obj.file_unique_id; mime=obj.mime_type or 'application/octet-stream'; size=obj.file_size or 0
        elif m.audio:
            obj=m.audio
            typ='audio'; fid=obj.file_id; name=obj.file_name or f'{obj.file_unique_id}.mp3'; mime=obj.mime_type or 'audio/mpeg'; size=obj.file_size or 0
        else:
            try: await m.delete()
            except: pass
            return

        file_unique_id=getattr(obj,'file_unique_id',None)
        # Backblaze path is limited to 20 MiB in this bot. Larger Telegram media
        # must NEVER be downloaded; Telegram file_id is already enough to send it.
        B2_MAX_BYTES=20*1024*1024

        def file_id_record():
            return {
                'telegram_file_id':fid,
                'telegram_file_unique_id':file_unique_id,
                'drive_account':None,
                'drive_file_id':None,
                'type':typ,
                'file_name':name,
                'file_size':size,
                'mime_type':mime,
                'storage_status':'telegram_file_id_only',
            }

        try:
            # IMPORTANT: no getFile/download for >20 MiB.
            if size > B2_MAX_BYTES:
                media.append(file_id_record())
                await state.update_data(media=media)
                if status_id:
                    try:
                        await m.bot.edit_message_text(
                            chat_id=m.chat.id,
                            message_id=status_id,
                            text=(f'📤 <b>UP FILE</b>\n\n'
                                  f'✅ <b>{len(media)}/{MAX_MEDIA}</b> media diterima.\n\n'
                                  f'📎 Ukuran: <b>{size / 1024 / 1024:.1f} MB</b>\n'
                                  '💾 Storage: <b>Telegram file_id</b>\n'
                                  'ℹ️ Media di atas 20 MB tidak dikirim ke B2.\n\n'
                                  'Tekan <b>✅ Selesai Upload</b> untuk lanjut.'),
                            parse_mode='HTML',reply_markup=media_kb())
                    except: pass
                try: await m.delete()
                except: pass
                return

            # Small media still goes to B2 when available. If B2 is unavailable,
            # keep the Telegram file_id instead of rejecting the upload.
            if not b2_pool.available:
                media.append(file_id_record())
                await state.update_data(media=media)
                if status_id:
                    try:
                        await m.bot.edit_message_text(
                            chat_id=m.chat.id,message_id=status_id,
                            text=(f'📤 <b>UP FILE</b>\n\n'
                                  f'✅ <b>{len(media)}/{MAX_MEDIA}</b> media diterima.\n\n'
                                  '⚠️ B2 tidak tersedia. Media disimpan menggunakan <b>Telegram file_id</b>.'),
                            parse_mode='HTML',reply_markup=media_kb())
                    except: pass
                try: await m.delete()
                except: pass
                return

            if status_id:
                try:
                    await m.bot.edit_message_text(
                        chat_id=m.chat.id,message_id=status_id,
                        text=f'⏳ <b>Loading…</b>\n\n📤 Menyimpan media <b>{len(media)+1}/{MAX_MEDIA}</b>',
                        parse_mode='HTML',reply_markup=media_kb())
                except: pass

            fd,path=tempfile.mkstemp(prefix='pastele_')
            os.close(fd)
            try:
                f=await m.bot.get_file(fid)
                await m.bot.download_file(f.file_path,path)
                account,key,_=await b2_pool.upload(path,name,mime)
                media.append({
                    'telegram_file_id':fid,
                    'telegram_file_unique_id':file_unique_id,
                    'drive_account':account,
                    'drive_file_id':key,
                    'type':typ,
                    'file_name':name,
                    'file_size':size,
                    'mime_type':mime,
                    'storage_status':'b2_available'
                })
            except Exception as exc:
                # B2 failure is non-fatal. Preserve the media through file_id.
                media.append(file_id_record())
                await state.update_data(media=media)
                try:
                    await (await get_pool()).execute(
                        "INSERT INTO error_logs(source,message,user_id) VALUES($1,$2,$3)",
                        'upfile_b2_fallback',str(exc)[:1000],uid)
                except: pass
                try:
                    from utils.notify_channel import notify
                    await notify(m.bot,
                        f'⚠️ <b>UP FILE — B2 FALLBACK</b>\n\n'
                        f'🆔 User: <code>{uid}</code>\n'
                        f'📎 File: <code>{html.escape(name)}</code>\n'
                        f'❌ <code>{html.escape(str(exc)[:700])}</code>')
                except: pass
            finally:
                try: os.remove(path)
                except: pass
                path=None

            await state.update_data(media=media)
            if status_id:
                try:
                    await m.bot.edit_message_text(
                        chat_id=m.chat.id,message_id=status_id,
                        text=(f'📤 <b>UP FILE</b>\n\n'
                              f'✅ <b>{len(media)}/{MAX_MEDIA}</b> media diterima.\n\n'
                              'Tekan <b>✅ Selesai Upload</b> untuk lanjut.'),
                        parse_mode='HTML',reply_markup=media_kb())
                except: pass
            try: await m.delete()
            except: pass

        except Exception as exc:
            try: await m.delete()
            except: pass
            try:
                await (await get_pool()).execute(
                    "INSERT INTO error_logs(source,message,user_id) VALUES($1,$2,$3)",
                    'upfile',str(exc)[:1000],uid)
            except: pass
            if status_id:
                try:
                    await m.bot.edit_message_text(
                        chat_id=m.chat.id,message_id=status_id,
                        text=(f'❌ <b>Gagal memproses media.</b>\n\n'
                              f'📦 Tersimpan: <b>{len(media)}/{MAX_MEDIA}</b>'),
                        parse_mode='HTML',reply_markup=media_kb())
                except: pass
        finally:
            if path:
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
    await state.update_data(tags=tags)

    # Creator flow: media -> title -> tags -> price -> create.
    # Free/VIP flow: media -> title -> tags -> create directly.
    creator=await is_creator(m.from_user.id)
    if creator:
        await state.set_state(U.price)
        await m.answer(
            f'💰 <b>MASUKKAN HARGA CODE</b>\n\n'
            f'Creator dapat membuat paid code.\n'
            f'Minimal Rp{PAID_CODE_MIN_IDR:,} • Maksimal Rp{PAID_CODE_MAX_IDR:,} • kelipatan Rp1.000\n'
            f'Kirim <code>0</code> untuk FREE.'.replace(',','.'),
            parse_mode='HTML')
        return

    # Non-creator users (FREE/VIP) create a FREE code directly after tags.
    await create_code(m, state, 0)


async def create_code(m,state,price:int):
    d=await state.get_data()
    media=d.get('media',[])
    title=d.get('title','Untitled')
    tags=d.get('tags',[])
    if not media:
        await state.clear()
        return await m.answer('❌ Media tidak ditemukan. Silakan mulai UP FILE lagi.')

    counts=[
        sum(x['type']=='photo' for x in media),
        sum(x['type']=='video' for x in media),
        sum(x['type']=='document' for x in media),
    ]
    code=await new_code(counts)
    p=await get_pool()
    value=len(media)*100
    creator=await is_creator(m.from_user.id)
    from config import OWNER_ID,ADMIN_IDS
    admin=m.from_user.id==OWNER_ID or m.from_user.id in ADMIN_IDS

    # Upload reward is ONLY for FREE/VIP users. Approved creators do not receive
    # upload points. Admins also do not receive the reward.
    vip=False
    try:
        from utils.economy import is_vip
        vip=await is_vip(m.from_user.id)
    except Exception:
        vip=False
    reward_eligible=(not creator and not admin and (vip or not vip))

    async with p.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT user_id FROM users WHERE user_id=$1 FOR UPDATE",
                m.from_user.id
            )
            await conn.execute("""INSERT INTO files(code,owner_id,title,media,media_count,photo_count,video_count,document_count,audio_count,code_value_idr,tags,price_idr)
            VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10,$11,$12)""",
            code,m.from_user.id,title,json.dumps(media),len(media),counts[0],counts[1],counts[2],
            sum(x['type']=='audio' for x in media),value,tags,price)

            if reward_eligible:
                # Every 10 cumulative media = +1 point.
                # The unique reference prevents the same milestone from being
                # awarded twice after retries/redeploys.
                total_uploaded=await conn.fetchval(
                    "SELECT COALESCE(SUM(media_count),0) FROM files WHERE owner_id=$1",
                    m.from_user.id
                )
                milestones=int(total_uploaded)//10
                for milestone in range(1,milestones+1):
                    reference=f"upload_reward:{m.from_user.id}:{milestone}"
                    inserted=await conn.fetchval(
                        """INSERT INTO point_transactions(user_id,amount,type,reference)
                           VALUES($1,1,'upload',$2)
                           ON CONFLICT(reference) DO NOTHING
                           RETURNING id""",
                        m.from_user.id,reference
                    )
                    if inserted:
                        await conn.execute(
                            "UPDATE users SET points=points+1 WHERE user_id=$1",
                            m.from_user.id
                        )

    await state.clear()
    tagtext=' '.join('#'+html.escape(t) for t in tags) or '-'
    lang = await get_lang(m.from_user.id) or 'id'
    labels = {
        'id': ('Sukses Membuat', 'Judul', 'Tag', 'Tipe', 'Bot', 'media', 'gratis', 'berbayar'),
        'en': ('Success Create', 'Title', 'Tag', 'Type', 'Bot', 'media', 'free', 'paid'),
        'zh': ('创建成功', '标题', '标签', '类型', '机器人', '媒体', '免费', '付费'),
    }
    success, lbl_title, lbl_tag, lbl_type, lbl_bot, lbl_media, free_txt, paid_txt = labels.get(lang, labels['id'])
    type_text = paid_txt if price > 0 else free_txt
    bot_name = str(BOT_USERNAME or '').strip().lstrip('@')
    bot_text = f'@{html.escape(bot_name)}' if bot_name else '-'
    await m.answer(
        f'✅ <b>{success}</b>\n'
        f'📝 {lbl_title}: {html.escape(title)}\n'
        f'🏷 {lbl_tag}: {tagtext}\n'
        f'🔑 Code: <code>{html.escape(code)}</code>\n'
        f'🤖 {lbl_bot}: {bot_text}\n'
        f'📦 {len(media)} {lbl_media}\n'
        f'🏷 {lbl_type}: {type_text}',
        parse_mode='HTML')


@router.message(U.price)
async def price(m,state):
    d=await state.get_data()
    try:
        price=int(re.sub(r'\D','',m.text or ''))
    except:
        price=-1
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
    await create_code(m,state,price)

@router.callback_query(F.data=='up_cancel')
async def cancel(c,state):
    await loading(c); await state.clear(); await c.message.edit_text('❌ Upload dibatalkan.')
