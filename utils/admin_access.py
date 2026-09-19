from __future__ import annotations
import os
from database import get_pool


def _parse_ids(*names: str) -> set[int]:
    out: set[int] = set()
    for name in names:
        raw = os.getenv(name, "") or ""
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                try:
                    out.add(int(part))
                except Exception:
                    pass
    return out


def configured_admin_ids() -> set[int]:
    ids = _parse_ids("OWNER_ID", "OWNER_IDS", "ADMINS", "ADMIN_IDS")
    return {x for x in ids if x != 0}


def is_config_admin(user_id: int) -> bool:
    try:
        return int(user_id) in configured_admin_ids()
    except Exception:
        return False


async def admin_access(user_id: int) -> bool:
    """Single source of truth for admin authorization.

    Accepts Railway env IDs and DB users.is_admin. DB failures never grant access.
    """
    try:
        uid = int(user_id)
    except Exception:
        return False
    if uid in configured_admin_ids():
        return True
    try:
        p = await get_pool()
        row = await p.fetchrow(
            "SELECT COALESCE(is_admin,FALSE) AS is_admin FROM users WHERE user_id=$1::BIGINT",
            uid,
        )
        return bool(row and row["is_admin"])
    except Exception:
        return False


def admin_env_debug(user_id: int) -> dict:
    ids = configured_admin_ids()
    return {
        "user_id": int(user_id),
        "is_admin_env": int(user_id) in ids,
        "owner_id": os.getenv("OWNER_ID", ""),
        "admins": os.getenv("ADMINS", ""),
        "admin_ids": os.getenv("ADMIN_IDS", ""),
        "owner_ids": os.getenv("OWNER_IDS", ""),
    }
