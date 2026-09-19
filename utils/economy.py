from decimal import Decimal
from datetime import datetime,timedelta,timezone,date
from database import get_pool
from config import POINT_UNLOCK_HOURS,STAR_UNLOCK_HOURS,STAR_PER_MEDIA,CREATOR_POINT_DISCOUNT,CREATOR_SHARE_PERCENT
async def ensure_user(uid,username=None,name=None):
    p=await get_pool(); await p.execute("""INSERT INTO users(user_id,username,full_name) VALUES($1,$2,$3) ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,full_name=EXCLUDED.full_name,last_seen=NOW()""",uid,username,name)
async def is_creator(uid):
    p=await get_pool(); return bool(await p.fetchval("SELECT is_creator AND creator_status='approved' FROM users WHERE user_id=$1",uid) or False)
async def checkin(uid):
    p=await get_pool(); today=date.today()
    async with p.acquire() as c:
        async with c.transaction():
            r=await c.fetchrow("SELECT points,last_checkin_date,checkin_streak FROM users WHERE user_id=$1 FOR UPDATE",uid)
            if not r: return Decimal(0),0,False
            if r["last_checkin_date"]==today: return Decimal(str(r["points"])),int(r["checkin_streak"]),False
            streak=int(r["checkin_streak"] or 0)+1 if r["last_checkin_date"] and r["last_checkin_date"]==today-timedelta(days=1) else 1
            if streak>7: streak=1
            reward=Decimal("1.00") if streak==7 else Decimal("0.10")
            await c.execute("UPDATE users SET points=points+$1,last_checkin_date=$2,checkin_streak=$3 WHERE user_id=$4",reward,today,streak,uid)
            await c.execute("INSERT INTO point_transactions(user_id,amount,type,reference) VALUES($1,$2,'checkin',$3) ON CONFLICT(reference) DO NOTHING",uid,reward,f"checkin:{uid}:{today}")
            bal=await c.fetchval("SELECT points FROM users WHERE user_id=$1",uid)
            return Decimal(str(bal)),streak,True
async def unlock(uid,code,media_count,method):
    p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            f=await c.fetchrow("SELECT owner_id,code_value_idr,active FROM files WHERE lower(code)=lower($1) FOR UPDATE",code)
            if not f or not f["active"]: return False,Decimal(0),"notfound",0
            creator_user=await c.fetchrow("SELECT is_creator,creator_status FROM users WHERE user_id=$1",uid)
            creator=bool(creator_user and creator_user["is_creator"] and creator_user["creator_status"]=="approved")
            if method=="points":
                cost=(Decimal(media_count)*Decimal("0.5") if creator else Decimal(media_count)).quantize(Decimal("0.01")); hours=POINT_UNLOCK_HOURS
            else:
                cost=(Decimal(media_count)*Decimal(str(STAR_PER_MEDIA))).quantize(Decimal("0.01")); hours=STAR_UNLOCK_HOURS
            balcol="points" if method=="points" else "stars"
            bal=Decimal(str(await c.fetchval(f"SELECT {balcol} FROM users WHERE user_id=$1 FOR UPDATE",uid) or 0))
            if bal<cost: return False,bal,"insufficient",cost
            await c.execute(f"UPDATE users SET {balcol}={balcol}-$1 WHERE user_id=$2",cost,uid)
            expires=datetime.now(timezone.utc)+timedelta(hours=hours)
            creator_id=int(f["owner_id"])
            value=Decimal(str(f["code_value_idr"] or 0))
            income=(value*Decimal(str(CREATOR_SHARE_PERCENT))/Decimal(100)).quantize(Decimal("0.01"))
            await c.execute("""INSERT INTO unlock_transactions(user_id,creator_id,code,payment_type,amount,creator_reward_points,creator_income_idr,expires_at) VALUES($1,$2,$3,$4,$5,1,$6,$7)""",uid,creator_id,code,method,cost,income,expires)
            await c.execute("UPDATE users SET total_unlocks=total_unlocks+1 WHERE user_id=$1",uid)
            if creator_id!=uid:
                await c.execute("UPDATE users SET points=points+1 WHERE user_id=$1",creator_id)
                await c.execute("INSERT INTO point_transactions(user_id,amount,type,reference) VALUES($1,1,'unlock_reward',$2)",creator_id,f"unlock:{uid}:{code}:{method}:{datetime.now(timezone.utc).timestamp()}")
                await c.execute("UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1 WHERE user_id=$2",income,creator_id)
            return True,bal-cost,"ok",cost
