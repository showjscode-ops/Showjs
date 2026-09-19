import os
from dotenv import load_dotenv
load_dotenv()

def env_int(name, default=0):
    try: return int(str(os.getenv(name, default)).strip())
    except Exception: return default

def env_bool(name, default=False):
    return str(os.getenv(name, str(default))).strip().lower() in {"1","true","yes","on"}

BOT_TOKEN=os.getenv("BOT_TOKEN","").strip()
BOT_USERNAME=os.getenv("BOT_USERNAME","Showjsbot").lstrip("@").strip()
DATABASE_URL=os.getenv("DATABASE_URL","").strip()
PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL","").strip().rstrip("/")
OWNER_ID=env_int("OWNER_ID")
ADMIN_IDS={int(x.strip()) for x in os.getenv("ADMIN_IDS","").replace(";",",").split(",") if x.strip().lstrip("-").isdigit()}
NOTIF_CHANNEL_ID=env_int("NOTIF_CHANNEL_ID")
# Mandatory subscription channels. If IDs are empty, that channel is skipped.
FORCE_CHANNEL_ID=env_int("FORCE_CHANNEL_ID", env_int("FORCE_CHANNEL", 0))
NOTICE_SUB_CHANNEL_ID=env_int("NOTICE_SUB_CHANNEL_ID", env_int("NOTICE_CHANNEL_ID", NOTIF_CHANNEL_ID))
FORCE_CHANNEL_URL=os.getenv("FORCE_CHANNEL_URL","").strip()
NOTICE_SUB_CHANNEL_URL=os.getenv("NOTICE_SUB_CHANNEL_URL", os.getenv("NOTIF_CHANNEL_URL","")).strip()
FORCE_CHANNEL_USERNAME=os.getenv("FORCE_CHANNEL_USERNAME","").strip().lstrip("@")
NOTICE_SUB_CHANNEL_USERNAME=os.getenv("NOTICE_SUB_CHANNEL_USERNAME", os.getenv("NOTIF_CHANNEL_USERNAME","")).strip().lstrip("@")
CODE_GROUP_ID=env_int("CODE_GROUP_ID")
CODE_GROUP_URL=os.getenv("CODE_GROUP_URL","").strip()
CODE_GROUP_TITLE=os.getenv("CODE_GROUP_TITLE","Group Chat Code").strip() or "Group Chat Code"
NOTICE_CHANNEL_URL=os.getenv("NOTICE_CHANNEL_URL", os.getenv("NOTIF_CHANNEL_URL","")).strip()
WITHDRAW_CHANNEL_ID=env_int("WITHDRAW_CHANNEL_ID")
TIMEZONE="Asia/Jakarta"

# Payments
BAYARGG_API_KEY=os.getenv("BAYARGG_API_KEY","").strip()
BAYARGG_SECRET=os.getenv("BAYARGG_SECRET","").strip()
BAYARGG_WEBHOOK_SECRET=os.getenv("BAYARGG_WEBHOOK_SECRET","").strip()
BAYARGG_BASE_URL=os.getenv("BAYARGG_BASE_URL","https://www.bayar.gg/api").strip().rstrip("/")
BAYARGG_WEBHOOK_URL=f"{PUBLIC_BASE_URL}/bayargg/webhook" if PUBLIC_BASE_URL else ""
CASHI_API_KEY=os.getenv("CASHI_API_KEY","").strip()
CASHI_BASE_URL=os.getenv("CASHI_BASE_URL","https://cashi.id").strip().rstrip("/")
CASHI_PAYMENT_CHANNEL=os.getenv("CASHI_PAYMENT_CHANNEL","QRIS_CUSTOM").strip()
CASHI_MIN_AMOUNT=env_int("CASHI_MIN_AMOUNT",2000)
CASHI_MAX_AMOUNT=env_int("CASHI_MAX_AMOUNT",10000000)

# Storage: up to 10 service accounts. Each JSON must have its own Drive folder shared to that account.
GOOGLE_DRIVE_COUNT=min(max(env_int("GOOGLE_DRIVE_COUNT",10),1),10)

# Bot rules
MAX_MEDIA=env_int("MAX_MEDIA",50)
POINT_UNLOCK_HOURS=24
STAR_UNLOCK_HOURS=48
STAR_PER_MEDIA=0.02  # 25 media=0.5 Star, 50=1 Star
CREATOR_POINT_DISCOUNT=0.50
CREATOR_SHARE_PERCENT=20.0  # Rp5,000 code value => Rp1,000 creator earnings
PLATFORM_FEE_PERCENT=80.0
POINT_PACKAGES={25:5000,50:10000,75:13000,100:15000,200:20000}
STAR_PACKAGES={1:10000,2:15000,3:17000,5:20000}
TRIAL_POINTS=2.0
TRIAL_STARS=2.0
