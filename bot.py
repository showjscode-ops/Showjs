from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from middlewares.subscription import SubscriptionMiddleware
bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode='HTML')); dp=Dispatcher()
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())
from handlers.start import router as start
from handlers.upfile import router as up
from handlers.getfile import router as getf
from handlers.payments import router as pay
from handlers.vip import router as vip
from handlers.creator import router as creator
from handlers.withdraw import router as wd
from handlers.misc import router as misc
from handlers.admin import router as admin
from handlers.trial import router as trial
for r in [start,up,getf,pay,vip,creator,wd,misc,admin,trial]:dp.include_router(r)
