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
 ('payment_bayargg_enabled','on'),('payment_cashi_enabled','on'),('trial_enabled','on'),('withdraw_enabled','on'),('maintenance','off')
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
 payment_type TEXT NOT NULL CHECK(payment_type IN('points','star')),
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
 purchase_type TEXT NOT NULL CHECK(purchase_type IN('points','stars','vip')),
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

CREATE INDEX IF NOT EXISTS idx_users_creator ON users(is_creator,creator_status);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen DESC);
COMMIT;
