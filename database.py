import os
import asyncpg
_pool=None
async def get_pool():
    global _pool
    if _pool is None:
        if not os.getenv("DATABASE_URL"):
            raise RuntimeError("DATABASE_URL belum diatur")
        _pool=await asyncpg.create_pool(os.getenv("DATABASE_URL"),min_size=1,max_size=10,statement_cache_size=0,ssl="require")
    return _pool
async def close_db():
    global _pool
    if _pool:
        await _pool.close(); _pool=None
async def init_db():
    await (await get_pool()).fetchval("SELECT 1")
async def execute(q,*a): return await (await get_pool()).execute(q,*a)
async def fetch(q,*a): return await (await get_pool()).fetch(q,*a)
async def fetchrow(q,*a): return await (await get_pool()).fetchrow(q,*a)
async def fetchval(q,*a): return await (await get_pool()).fetchval(q,*a)
