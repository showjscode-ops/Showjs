from __future__ import annotations
import html,json
from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from database import get_pool
from utils.economy import unlock,is_creator
from utils.media_sender import deliver_one
from utils.notify_channel import notify
from config import STAR_PER_MEDIA
from datetime import datetime,timezone
from utils.callback_loading import loading
router=Router()
def buttons(code,n,creator):
 p=n*0.5 if creator else n; s=n*STAR_PER_MEDIA
 return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'🪙 {p:g} Poin',callback_data=f'unlockp:{code}')],[InlineKeyboardButton(text=f'⭐ {s:g} Star',callback_data=f'unlocks:{code}')]])
async def show(m,code):
 p=await get_pool(); f=await p.fetchrow("SELECT * FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)
 if not f:return await m.answer('❌ Code tidak valid.')
 n=int(f['media_count']); c=await is_creator(m.from_user.id); pc=n*0.5 if c else n; sc=n*STAR_PER_MEDIA
 await m.answer(f'🔐 <b>MEDIA TERKUNCI</b>\n\n🔑 <code>{html.escape(code)}</code>\n📦 Total Media: <b>{n}</b>\n\n🪙 Poin: <b>{pc:g}</b>\n⭐ Star: <b>{sc:g}</b>\n\nPilih pembayaran:',parse_mode='HTML',reply_markup=buttons(code,n,c))
@router.callback_query(F.data=='getfile')
async def start(c): await loading(c); await c.message.answer('📥 Kirim CODE yang ingin dibuka.')
@router.message(F.text.regexp(r'^[A-Za-z0-9]+_[123456789XxYy]{11}_[0-9]+p[0-9]+v[0-9]+d$'))
async def receive(m):
    code=m.text.strip()
    await m.answer(
        f'🔑 <b>CODE TERDETEKSI</b>\n\n<code>{html.escape(code)}</code>\n\nTekan tombol di bawah untuk membuka media.',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📥 Get File',callback_data=f'getcode:{code}')]
        ])
    )

@router.callback_query(F.data.startswith('getcode:'))
async def getcode(c):
    await loading(c)
    await show(c.message,c.data.split(':',1)[1])

async def open_media(c,method):
 code=c.data.split(':',1)[1]; p=await get_pool(); f=await p.fetchrow("SELECT * FROM files WHERE lower(code)=lower($1) AND active=TRUE",code)
 if not f:return await c.answer('❌ Code tidak ditemukan.',show_alert=True)
 ok,new,reason,cost=await unlock(c.from_user.id,code,int(f['media_count']),method)
 if not ok:return await c.answer('❌ Saldo tidak cukup.' if reason=='insufficient' else '❌ Tidak dapat membuka media.',show_alert=True)
 await c.answer('✅ Pembayaran berhasil!'); hours=24 if method=='points' else 48; amount=f"{cost:g} {'Poin' if method=='points' else 'Star'}"; await notify(c.bot,f'📦 CODE UNLOCKED\n\n🆔 ID: {c.from_user.id}\n🔑 Code: {html.escape(code)}\n\n💳 Bayar: {amount}')
 media=f['media'] if isinstance(f['media'],list) else json.loads(f['media'] or '[]'); await c.message.edit_text(f'✅ <b>CODE TERBUKA</b>\n\n📦 {len(media)} media\n⏳ Akses berlaku {hours} jam.',parse_mode='HTML')
 from datetime import timedelta
 exp=datetime.now(timezone.utc)+timedelta(hours=hours)
 for i,item in enumerate(media,1):
  try:
   sent=await deliver_one(c.bot,c.from_user.id,item,caption=f'🔑 {code}-M{i:03d}\n📦 Media {i}/{len(media)}')
   if sent: await p.execute('INSERT INTO delivery_messages(user_id,chat_id,message_id,code,expires_at) VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING',c.from_user.id,c.from_user.id,sent.message_id,code,exp)
  except Exception: pass
@router.callback_query(F.data.startswith('unlockp:'))
async def up(c): await open_media(c,'points')
@router.callback_query(F.data.startswith('unlocks:'))
async def us(c): await open_media(c,'star')
