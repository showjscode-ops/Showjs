from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message
from database import get_pool
from config import OWNER_ID,TRIAL_POINTS,TRIAL_STARS
router=Router()
@router.message(Command('trial'))
async def trial(m):
 if m.from_user.id!=OWNER_ID:return
 p=await get_pool(); enabled=str(await p.fetchval("SELECT value FROM settings WHERE key='trial_enabled'") or 'off')=='on'
 if not enabled:return await m.answer('Trial sedang OFF di panel.')
 await p.execute('UPDATE users SET points=points+$1,stars=stars+$2 WHERE user_id=$3',TRIAL_POINTS,TRIAL_STARS,m.from_user.id); await p.execute('INSERT INTO trial_logs(owner_id,points_added,stars_added) VALUES($1,$2,$3)',m.from_user.id,TRIAL_POINTS,TRIAL_STARS); await m.answer(f'🧪 Trial masuk: +{TRIAL_POINTS:g} Poin dan +{TRIAL_STARS:g} Star.')
