import asyncio,logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from bot import bot,dp
from database import get_pool,close_db,init_db
from api.bayargg_webhook import router as bayar
from api.cashi_webhook import router as cashi
from tasks.payment_worker import worker as payment_worker
from tasks.expiry_worker import worker as expiry_worker
from tasks.subscription_worker import worker as subscription_worker
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
@asynccontextmanager
async def lifespan(app):
 await get_pool(); await init_db(); tasks=[asyncio.create_task(dp.start_polling(bot)),asyncio.create_task(payment_worker()),asyncio.create_task(expiry_worker()),asyncio.create_task(subscription_worker())]
 yield
 for t in tasks:t.cancel()
 await close_db(); await bot.session.close()
app=FastAPI(lifespan=lifespan); app.include_router(bayar); app.include_router(cashi)
@app.get('/')
async def root():return {'status':'running'}
@app.get('/health')
async def health():return {'status':'ok'}
