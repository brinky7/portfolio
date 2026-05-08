import time
from datetime import datetime, timezone
from bot.redis_client import _redis

RATE_LIMIT_TTL = 5  # seconds


def _day_key(user_id: int) -> str:
    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"quota_day:{user_id}:{d}"


def _month_key(user_id: int) -> str:
    m = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"quota_month:{user_id}:{m}"


def check_quota(user_id: int, tier: str, limits: dict) -> tuple[bool, str]:
    from bot.tiers import is_trial_expired

    if tier == "trial" and is_trial_expired(user_id):
        return False, "trial_expired"

    day_limit = limits.get("day")
    month_limit = limits.get("month")

    if day_limit is not None:
        from bot.referral import get_bonus
        used_day = int(_redis.get(_day_key(user_id)) or 0)
        if used_day >= day_limit and get_bonus(user_id) <= 0:
            return False, "day_limit"

    if month_limit is not None:
        used_month = int(_redis.get(_month_key(user_id)) or 0)
        if used_month >= month_limit:
            return False, "month_limit"

    return True, ""


def consume_quota(user_id: int) -> None:
    from bot.referral import consume_bonus
    if consume_bonus(user_id):
        return
    dk = _day_key(user_id)
    mk = _month_key(user_id)
    pipe = _redis.pipeline()
    pipe.incr(dk)
    pipe.expire(dk, 48 * 3600)
    pipe.incr(mk)
    pipe.expire(mk, 35 * 86400)
    pipe.execute()


def get_usage(user_id: int) -> tuple[int, int]:
    day = int(_redis.get(_day_key(user_id)) or 0)
    month = int(_redis.get(_month_key(user_id)) or 0)
    return day, month


def reset_day_quota(user_id: int) -> None:
    _redis.delete(_day_key(user_id))


def check_rate_limit(user_id: int) -> bool:
    key = f"ratelimit:{user_id}"
    if _redis.exists(key):
        return False
    _redis.set(key, 1, ex=RATE_LIMIT_TTL)
    return True
