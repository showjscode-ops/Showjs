BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users(
 user_id BIGINT PRIMARY KEY,
 username TEXT,
 full_name TEXT,
 points NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK(points>=0),
 stars NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK(stars>=0),
 is_creator BOOLEAN NOT NULL DEFAULT FALSE,
 creator_status TEXT NOT NULL DEFAULT 'none',
 earnings NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK(earnings>=0),
 total_sales BIGINT NOT NULL DEFAULT 0,
 total_unlocks BIGINT NOT NULL DEFAULT 0,
 is_admin BOOLEAN NOT NULL DEFAULT FALSE,
 vip BOOLEAN NOT NULL DEFAULT FALSE,
 vip_until TIMESTAMPTZ,
 checkin_streak INT NOT NULL DEFAULT 0,
 last_checkin_date DATE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 subscription_notice_at TIMESTAMPTZ
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_notice_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL DEFAULT '');
INSERT INTO settings(key,value) VALUES
 ('payment_bayargg_enabled','on'),('payment_cashi_enabled','on'),('payment_manual_enabled','on'),('payment_balance_enabled','on'),
 ('trial_enabled','on'),('withdraw_enabled','on'),('maintenance','off'),('vip_code_delay_minutes','30'),('media_send_delay_ms','250'),
 ('manual_qr_file_id',''),('preferred_b2_account','0')
 ON CONFLICT(key) DO NOTHING;

CREATE TABLE IF NOT EXISTS admins(user_id BIGINT PRIMARY KEY,role TEXT NOT NULL DEFAULT 'admin',created_at TIMESTAMPTZ DEFAULT NOW());

CREATE TABLE IF NOT EXISTS files(
 id BIGSERIAL PRIMARY KEY,
 code TEXT UNIQUE NOT NULL,
 owner_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
 title TEXT,
 media JSONB NOT NULL DEFAULT '[]'::jsonb,
 media_count INT NOT NULL DEFAULT 0,
 photo_count INT NOT NULL DEFAULT 0,
 video_count INT NOT NULL DEFAULT 0,
 document_count INT NOT NULL DEFAULT 0,
 audio_count INT NOT NULL DEFAULT 0,
 code_value_idr NUMERIC(18,2) NOT NULL DEFAULT 0,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_files_owner ON files(owner_id);
CREATE INDEX IF NOT EXISTS idx_files_code_lower ON files(LOWER(code));

CREATE TABLE IF NOT EXISTS code_group_shares(
 id BIGSERIAL PRIMARY KEY,code TEXT NOT NULL,group_id BIGINT NOT NULL,shared_by BIGINT NOT NULL,first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(code,group_id)
);

CREATE TABLE IF NOT EXISTS unlock_transactions(
 id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
 creator_id BIGINT,
 code TEXT NOT NULL,
 payment_type TEXT NOT NULL CHECK(payment_type IN('points','star','balance')),
 amount NUMERIC(18,2) NOT NULL,
 creator_reward_points NUMERIC(18,2) NOT NULL DEFAULT 1,
 creator_income_idr NUMERIC(18,2) NOT NULL DEFAULT 0,
 expires_at TIMESTAMPTZ NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_unlock_user_code ON unlock_transactions(user_id,code);
CREATE INDEX IF NOT EXISTS idx_unlock_expiry ON unlock_transactions(expires_at);

CREATE TABLE IF NOT EXISTS delivery_messages(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,chat_id BIGINT NOT NULL,message_id BIGINT NOT NULL,code TEXT NOT NULL,expires_at TIMESTAMPTZ NOT NULL,UNIQUE(chat_id,message_id)
);
CREATE INDEX IF NOT EXISTS idx_delivery_expiry ON delivery_messages(expires_at);

CREATE TABLE IF NOT EXISTS point_transactions(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,amount NUMERIC(18,2) NOT NULL,type TEXT NOT NULL,reference TEXT UNIQUE NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS star_transactions(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,amount NUMERIC(18,2) NOT NULL,type TEXT NOT NULL,reference TEXT UNIQUE NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchases(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
 purchase_type TEXT NOT NULL CHECK(purchase_type IN('points','stars','vip','creator','deposit','file')),
 quantity NUMERIC(18,2) NOT NULL DEFAULT 0,
 amount BIGINT NOT NULL,
 provider TEXT NOT NULL,
 order_id TEXT UNIQUE NOT NULL,
 invoice_id TEXT UNIQUE,
 status TEXT NOT NULL DEFAULT 'pending',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_purchases_pending ON purchases(status,created_at);
CREATE INDEX IF NOT EXISTS idx_purchases_invoice ON purchases(invoice_id);

CREATE TABLE IF NOT EXISTS withdraws(
 id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,amount NUMERIC(18,2) NOT NULL,method TEXT NOT NULL,account TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),processed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS trial_logs(
 id BIGSERIAL PRIMARY KEY,owner_id BIGINT NOT NULL,points_added NUMERIC(18,2) NOT NULL DEFAULT 0,stars_added NUMERIC(18,2) NOT NULL DEFAULT 0,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vip_packages(
 code TEXT PRIMARY KEY,name TEXT NOT NULL,price BIGINT NOT NULL,duration_days INT NOT NULL DEFAULT 30,active BOOLEAN NOT NULL DEFAULT TRUE
);
INSERT INTO vip_packages(code,name,price,duration_days) VALUES
 ('vip1','VIP 1 Hari',20000,1),('vip3','VIP 3 Hari',40000,3),('vip5','VIP 5 Hari',60000,5),('vip7','VIP 7 Hari',80000,7),('vip10','VIP 10 Hari',100000,10),('vip15','VIP 15 Hari',130000,15)
 ON CONFLICT(code) DO NOTHING;

ALTER TABLE users ADD COLUMN IF NOT EXISTS balance NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS can_unlock BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE files ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
ALTER TABLE files ADD COLUMN IF NOT EXISTS price_idr NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE files ADD COLUMN IF NOT EXISTS views BIGINT NOT NULL DEFAULT 0;
ALTER TABLE files ADD COLUMN IF NOT EXISTS likes BIGINT NOT NULL DEFAULT 0;
ALTER TABLE files ADD COLUMN IF NOT EXISTS hates BIGINT NOT NULL DEFAULT 0;
ALTER TABLE files ADD COLUMN IF NOT EXISTS favorites BIGINT NOT NULL DEFAULT 0;
-- Media JSONB entries now retain telegram_file_id and telegram_file_unique_id as fallback metadata.

ALTER TABLE purchases ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS code_reactions(user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,code TEXT REFERENCES files(code) ON DELETE CASCADE,reaction TEXT CHECK(reaction IN('like','hate','favorite')),created_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(user_id,code,reaction));
CREATE TABLE IF NOT EXISTS code_cooldowns(user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,code TEXT NOT NULL,opened_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(user_id,code));
CREATE TABLE IF NOT EXISTS manual_deposits(id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,amount NUMERIC(18,2) NOT NULL,proof_file_id TEXT,proof_type TEXT,target_code TEXT,target_type TEXT,quantity NUMERIC(18,2) DEFAULT 0,status TEXT NOT NULL DEFAULT 'pending',admin_id BIGINT,note TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),processed_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS error_logs(id BIGSERIAL PRIMARY KEY,level TEXT DEFAULT 'ERROR',source TEXT,message TEXT,user_id BIGINT,created_at TIMESTAMPTZ DEFAULT NOW());
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
CREATE INDEX IF NOT EXISTS idx_b2_storage_accounts_enabled ON b2_storage_accounts(enabled);

CREATE TABLE IF NOT EXISTS b2_storage_moves(id BIGSERIAL PRIMARY KEY,code TEXT,from_account INT,to_account INT,moved_count INT DEFAULT 0,status TEXT DEFAULT 'pending',error TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),finished_at TIMESTAMPTZ);
ALTER TABLE manual_deposits ADD COLUMN IF NOT EXISTS target_code TEXT;
CREATE INDEX IF NOT EXISTS idx_code_reactions_code ON code_reactions(code);
CREATE INDEX IF NOT EXISTS idx_manual_deposits_status ON manual_deposits(status,created_at);

CREATE INDEX IF NOT EXISTS idx_users_creator ON users(is_creator,creator_status);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen DESC);
COMMIT;


-- PAYMENT SETTINGS: one canonical key per payment method.
INSERT INTO settings(key,value) VALUES
 ('payment_bayargg_enabled','on'),
 ('payment_cashi_enabled','on'),
 ('payment_manual_enabled','on'),
 ('payment_balance_enabled','on')
ON CONFLICT(key) DO NOTHING;

ALTER TABLE purchases DROP CONSTRAINT IF EXISTS purchases_purchase_type_check;
ALTER TABLE purchases ADD CONSTRAINT purchases_purchase_type_check CHECK(purchase_type IN('points','stars','vip','creator','deposit','file'));
ALTER TABLE purchases ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_message_id BIGINT;
ALTER TABLE purchases ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE manual_deposits ADD COLUMN IF NOT EXISTS qr_message_id BIGINT;
ALTER TABLE manual_deposits ADD COLUMN IF NOT EXISTS proof_message_id BIGINT;


-- V24 creator economy / manual unlock / role controls
ALTER TABLE users ADD COLUMN IF NOT EXISTS creator_last_paid_upload_date DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS creator_paid_upload_count_today INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS creator_extra_opens NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS creator_previous BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS creator_daily_opens(
 user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
 open_date DATE NOT NULL,
 used_count INT NOT NULL DEFAULT 0,
 PRIMARY KEY(user_id,open_date)
);
CREATE INDEX IF NOT EXISTS idx_creator_daily_opens_date ON creator_daily_opens(open_date);

ALTER TABLE unlock_transactions DROP CONSTRAINT IF EXISTS unlock_transactions_payment_type_check;
ALTER TABLE unlock_transactions ADD CONSTRAINT unlock_transactions_payment_type_check
 CHECK(payment_type IN('points','star','balance','qr','creator_points','admin'));

CREATE INDEX IF NOT EXISTS idx_unlock_creator_paid_members ON unlock_transactions(creator_id,payment_type,user_id);

INSERT INTO settings(key,value) VALUES
 ('creator_daily_base_paid_opens','1'),
 ('creator_members_per_extra_open','10'),
 ('creator_point_discount','0.50'),
 ('creator_registration_fee_idr','200000'),
 ('creator_renewal_percent','30'),
 ('paid_code_min_idr','2000'),
 ('paid_code_max_idr','2000000')
 ON CONFLICT(key) DO NOTHING;
