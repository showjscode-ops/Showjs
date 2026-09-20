
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
    p=await get_pool()
    await p.execute("""
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL DEFAULT '');
    INSERT INTO settings(key,value) VALUES
      ('payment_bayargg_enabled','on'),('payment_cashi_enabled','on'),
      ('payment_manual_enabled','on'),('payment_balance_enabled','on'),
      ('trial_enabled','on'),('withdraw_enabled','on'),('maintenance','off'),
      ('vip_code_delay_minutes','30'),('media_send_delay_ms','250'),
      ('manual_qr_file_id',''),('preferred_b2_account','0')
    ON CONFLICT(key) DO NOTHING;

    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC(18,2) NOT NULL DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS can_unlock BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_started_at TIMESTAMPTZ;

    ALTER TABLE files ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
    ALTER TABLE files ADD COLUMN IF NOT EXISTS price_idr NUMERIC(18,2) NOT NULL DEFAULT 0;
    ALTER TABLE files ADD COLUMN IF NOT EXISTS views BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE files ADD COLUMN IF NOT EXISTS likes BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE files ADD COLUMN IF NOT EXISTS hates BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE files ADD COLUMN IF NOT EXISTS favorites BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

    CREATE TABLE IF NOT EXISTS code_reactions(
      user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
      code TEXT NOT NULL REFERENCES files(code) ON DELETE CASCADE,
      reaction TEXT NOT NULL CHECK(reaction IN ('like','hate','favorite')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(user_id,code,reaction)
    );

    CREATE TABLE IF NOT EXISTS code_cooldowns(
      user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
      code TEXT NOT NULL,
      opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(user_id,code)
    );

    CREATE TABLE IF NOT EXISTS manual_deposits(
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
      amount NUMERIC(18,2) NOT NULL,
      proof_file_id TEXT,
      proof_type TEXT,
      target_code TEXT,
      target_type TEXT,
      quantity NUMERIC(18,2) DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'pending',
      admin_id BIGINT,
      note TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      processed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS error_logs(
      id BIGSERIAL PRIMARY KEY,
      level TEXT NOT NULL DEFAULT 'ERROR',
      source TEXT,
      message TEXT NOT NULL,
      user_id BIGINT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS b2_storage_accounts(
      account_id INT PRIMARY KEY CHECK(account_id BETWEEN 1 AND 10),
      name TEXT NOT NULL DEFAULT '',
      endpoint TEXT NOT NULL,
      region TEXT NOT NULL,
      bucket TEXT NOT NULL,
      key_id TEXT NOT NULL,
      application_key TEXT NOT NULL,
      enabled BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

        CREATE TABLE IF NOT EXISTS b2_storage_moves(
      id BIGSERIAL PRIMARY KEY,
      code TEXT,
      from_account INT,
      to_account INT,
      moved_count INT NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'pending',
      error TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      finished_at TIMESTAMPTZ
    );

    -- Existing deployments may have the old unlock payment constraint.
    ALTER TABLE IF EXISTS unlock_transactions DROP CONSTRAINT IF EXISTS unlock_transactions_payment_type_check;
    ALTER TABLE IF EXISTS unlock_transactions ADD CONSTRAINT unlock_transactions_payment_type_check CHECK(payment_type IN ('points','star','balance'));

    CREATE INDEX IF NOT EXISTS idx_manual_deposits_status ON manual_deposits(status,created_at);
    CREATE INDEX IF NOT EXISTS idx_error_logs_created ON error_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_code_reactions_code ON code_reactions(code);
    CREATE INDEX IF NOT EXISTS idx_files_tags ON files USING GIN(tags);
    """)
    await p.execute("""
    INSERT INTO users(user_id,is_admin)
    SELECT $1::BIGINT,TRUE
    WHERE $1::BIGINT <> 0
    ON CONFLICT(user_id) DO UPDATE SET is_admin=TRUE
    """, int(os.getenv("OWNER_ID","0") or 0))
    await p.fetchval("SELECT 1")

async def execute(q,*a): return await (await get_pool()).execute(q,*a)
async def fetch(q,*a): return await (await get_pool()).fetch(q,*a)
async def fetchrow(q,*a): return await (await get_pool()).fetchrow(q,*a)
async def fetchval(q,*a): return await (await get_pool()).fetchval(q,*a)
