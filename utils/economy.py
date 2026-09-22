
from decimal import Decimal
from datetime import datetime,timedelta,timezone,date
from database import get_pool
from config import POINT_UNLOCK_HOURS,STAR_UNLOCK_HOURS,STAR_PER_MEDIA,CREATOR_POINT_DISCOUNT,CREATOR_SHARE_PERCENT,CREATOR_DAILY_BASE_PAID_OPENS,CREATOR_MEMBERS_PER_EXTRA_OPEN,CREATOR_POINT_CREATOR_EARNING_PER_50_MEDIA_IDR

async def ensure_user(uid,username=None,name=None):
    p=await get_pool()
    await p.execute("""INSERT INTO users(user_id,username,full_name) VALUES($1,$2,$3)
    ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,full_name=EXCLUDED.full_name,last_seen=NOW()""",uid,username,name)

async def is_creator(uid):
    p=await get_pool()
    return bool(await p.fetchval("SELECT is_creator AND creator_status='approved' FROM users WHERE user_id=$1",uid) or False)

async def is_vip(uid):
    p=await get_pool()
    return bool(await p.fetchval("SELECT vip AND (vip_until IS NULL OR vip_until>NOW()) FROM users WHERE user_id=$1",uid) or False)

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

async def vip_allowed(uid,code):
    if not await is_vip(uid): return True
    p=await get_pool()
    r=await p.fetchval("SELECT opened_at FROM code_cooldowns WHERE user_id=$1 AND code=$2",uid,code)
    if not r: return True
    try: minutes=int(await p.fetchval("SELECT value FROM settings WHERE key='vip_code_delay_minutes'") or 30)
    except: minutes=30
    return datetime.now(timezone.utc)-r.replace(tzinfo=timezone.utc) >= timedelta(minutes=minutes)

async def creator_paid_open_quota(uid):
    """Daily free paid-code opens for creators: 1 base + 1 per 10 unique paid members."""
    p=await get_pool()
    if not await is_creator(uid): return 0,0
    members=await p.fetchval("""SELECT COUNT(DISTINCT user_id) FROM unlock_transactions
        WHERE creator_id=$1 AND payment_type IN ('qr','balance') AND user_id<>$1""",uid) or 0
    quota=int(CREATOR_DAILY_BASE_PAID_OPENS)+(int(members)//int(CREATOR_MEMBERS_PER_EXTRA_OPEN))
    used=await p.fetchval("SELECT used_count FROM creator_daily_opens WHERE user_id=$1 AND open_date=CURRENT_DATE",uid) or 0
    return quota,int(used)

async def creator_paid_upload_today(uid):
    p=await get_pool()
    return bool(await p.fetchval("SELECT 1 FROM files WHERE owner_id=$1 AND price_idr>0 AND created_at::date=CURRENT_DATE LIMIT 1",uid))

async def vip_daily_limit_for_days(days):
    """Daily code-open allowance for each VIP package duration."""
    mapping = {1:2, 3:4, 5:6, 7:7, 10:10, 15:15, 30:30}
    days=int(days or 0)
    if days in mapping:
        return mapping[days]
    # For future packages, use the package duration as the daily allowance,
    # with a minimum of 1. This keeps the rule deterministic without hardcoding
    # every possible package.
    return max(2, days)

async def vip_quota_status(conn, uid):
    user = await conn.fetchrow(
        "SELECT vip_plan_days,vip_daily_limit FROM users WHERE user_id=$1 FOR UPDATE", uid
    )
    limit = int(user["vip_daily_limit"] or 0) if user else 0
    if limit <= 0 and user:
        limit = await vip_daily_limit_for_days(int(user["vip_plan_days"] or 0))
    used = int(await conn.fetchval(
        "SELECT used_count FROM vip_daily_opens WHERE user_id=$1 AND open_date=CURRENT_DATE",
        uid
    ) or 0)
    return limit, used

async def unlock(uid,code,media_count,method):
    p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            f=await c.fetchrow("""
                SELECT owner_id,code_value_idr,price_idr,active
                FROM files WHERE lower(code)=lower($1) FOR UPDATE
            """,code)
            if not f or not f["active"]:
                return False,Decimal(0),"notfound",0

            user=await c.fetchrow("SELECT * FROM users WHERE user_id=$1 FOR UPDATE",uid)
            if not user or user["banned"] or not user["can_unlock"]:
                return False,Decimal(0),"blocked",0

            # The owner can always open their own code without spending anything.
            if int(f["owner_id"]) == int(uid):
                return True,Decimal(str(user["points"] or 0)),"own",0

            now=datetime.now(timezone.utc)
            vip=bool(user["vip"] and (user["vip_until"] is None or user["vip_until"]>now))
            if vip:
                limit, used = await vip_quota_status(c, uid)
                if limit > 0 and used >= limit:
                    return False,Decimal(0),"vip_quota",0

                await c.execute("""
                    INSERT INTO vip_daily_opens(user_id,open_date,used_count)
                    VALUES($1,CURRENT_DATE,1)
                    ON CONFLICT(user_id,open_date)
                    DO UPDATE SET used_count=vip_daily_opens.used_count+1
                """,uid)
                await c.execute("""
                    INSERT INTO code_cooldowns(user_id,code)
                    VALUES($1,$2)
                    ON CONFLICT(user_id,code) DO UPDATE SET opened_at=NOW()
                """,uid,code)
                await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)
                # Keep a 3-day access record so every delivered Telegram message
                # can be expired automatically and continuation can verify access.
                await c.execute("""
                    INSERT INTO unlock_transactions(
                        user_id,creator_id,code,payment_type,amount,
                        creator_reward_points,creator_income_idr,expires_at
                    ) VALUES($1,$2,$3,'balance',0,0,0,NOW()+INTERVAL '3 days')
                """,uid,int(f["owner_id"]),code)
                return True,Decimal(0),"vip",0

            # Re-opening an already unlocked code does not charge again while
            # its access window is still active.
            active = await c.fetchrow("""
                SELECT payment_type,expires_at
                FROM unlock_transactions
                WHERE user_id=$1 AND code=$2
                  AND payment_type IN ('points','star','balance')
                  AND expires_at>NOW()
                ORDER BY expires_at DESC LIMIT 1
            """,uid,code)
            if active:
                return True,Decimal(str(user["points"] or 0)), "active", 0

            price=Decimal(str(f["price_idr"] or 0))
            creator=bool(user["is_creator"] and user["creator_status"]=="approved")

            if method=="balance":
                if price<=0:
                    return False,Decimal(str(user["balance"] or 0)),"invalid_method",Decimal(0)
                bal=Decimal(str(user["balance"] or 0))
                if bal<price:
                    return False,bal,"insufficient",price

                await c.execute(
                    "UPDATE users SET balance=balance-$1,total_unlocks=total_unlocks+1 WHERE user_id=$2",
                    price,uid
                )
                creator_id=int(f["owner_id"])
                income=(price*Decimal(str(CREATOR_SHARE_PERCENT))/100).quantize(Decimal("0.01"))
                if creator_id!=uid:
                    await c.execute(
                        "UPDATE users SET earnings=earnings+$1,total_sales=total_sales+1,points=points+1 WHERE user_id=$2",
                        income,creator_id
                    )
                await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)

                exp=now+timedelta(days=3)
                await c.execute("""
                    INSERT INTO unlock_transactions(
                        user_id,creator_id,code,payment_type,amount,creator_reward_points,
                        creator_income_idr,expires_at
                    ) VALUES($1,$2,$3,'balance',$4,1,$5,$6)
                """,uid,creator_id,code,price,income,exp)
                return True,bal-price,"balance",price

            if method=="points":
                # Creator receives the same 50% media-price discount.
                cost=(Decimal(media_count) * (Decimal("0.50") if creator else Decimal("1"))).quantize(Decimal("0.01"))
                hours=POINT_UNLOCK_HOURS
                col="points"
            elif method=="star":
                # Star follows the same 50% creator discount.
                cost=(Decimal(media_count) * (Decimal(str(STAR_PER_MEDIA)) * (Decimal("0.50") if creator else Decimal("1")))).quantize(Decimal("0.01"))
                hours=STAR_UNLOCK_HOURS
                col="stars"
            else:
                return False,Decimal(0),"invalid_method",0

            bal=Decimal(str(user[col] or 0))
            if bal<cost:
                return False,bal,"insufficient",cost

            await c.execute(
                f"UPDATE users SET {col}={col}-$1,total_unlocks=total_unlocks+1 WHERE user_id=$2",
                cost,uid
            )
            creator_id=int(f["owner_id"])
            owner_is_creator=bool(await c.fetchval(
                "SELECT is_creator AND creator_status='approved' FROM users WHERE user_id=$1",
                creator_id
            ) or False)

            # Creator earnings:
            # Poin: Rp1,000 per 50 media, calculated linearly.
            # Example: 25 media = Rp500, 100 media = Rp2,000.
            # Star keeps the existing code-value-based creator reward.
            if method=="points" and owner_is_creator:
                income=(
                    Decimal(media_count)
                    * Decimal(str(CREATOR_POINT_CREATOR_EARNING_PER_50_MEDIA_IDR))
                    / Decimal("50")
                ).quantize(Decimal("0.01"))
            else:
                value=Decimal(str(f["code_value_idr"] or 0))
                income=(value*Decimal(str(CREATOR_SHARE_PERCENT))/100).quantize(Decimal("0.01"))

            exp=now+timedelta(hours=hours)

            await c.execute("""
                INSERT INTO unlock_transactions(
                    user_id,creator_id,code,payment_type,amount,creator_reward_points,
                    creator_income_idr,expires_at
                ) VALUES($1,$2,$3,$4,$5,1,$6,$7)
            """,uid,creator_id,code,method,cost,income,exp)

            if creator_id!=uid and owner_is_creator:
                await c.execute(
                    "UPDATE users SET points=points+1,earnings=earnings+$1,total_sales=total_sales+1 WHERE user_id=$2",
                    income,creator_id
                )


            await c.execute("UPDATE files SET views=views+1 WHERE code=$1",code)
            return True,bal-cost,"points" if method=="points" else "star",cost

