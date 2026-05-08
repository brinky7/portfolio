import os
import time
from bot.redis_client import _redis

ADMIN_USER_IDS: set[int] = {
    int(x) for x in os.environ.get("ADMIN_USER_IDS", "0").split(",") if x.strip()
}

TIER_LIMITS = {
    "trial": {"days": 3,    "day": 3,    "month": None},
    "basic": {"days": None, "day": 5,    "month": None},
    "pro":   {"days": None, "day": 15,   "month": None},
    "elite": {"days": None, "day": None, "month": None},
}


def get_tier(user_id: int) -> str:
    stored = _redis.get(f"tier:{user_id}")
    if stored:
        return stored
    if user_id in ADMIN_USER_IDS:
        return "elite"
    return "trial"


def set_tier(user_id: int, tier: str) -> None:
    _redis.set(f"tier:{user_id}", tier)


def get_tier_start(user_id: int) -> int | None:
    v = _redis.get(f"tier_start:{user_id}")
    return int(v) if v else None


def set_tier_start(user_id: int) -> None:
    if not _redis.exists(f"tier_start:{user_id}"):
        _redis.set(f"tier_start:{user_id}", int(time.time()))


def is_trial_expired(user_id: int) -> bool:
    start = get_tier_start(user_id)
    if start is None:
        return False
    return (time.time() - start) > 3 * 86400


def trial_days_left(user_id: int) -> int:
    start = get_tier_start(user_id)
    if start is None:
        return 3
    elapsed = (time.time() - start) / 86400
    return max(0, 3 - int(elapsed))


def get_tier_end(user_id: int) -> int | None:
    """Unix-timestamp истечения подписки, или None для trial/free."""
    ttl = _redis.ttl(f"tier:{user_id}")
    if ttl > 0:
        return int(time.time()) + ttl
    return None


def get_deposit(user_id: int) -> float | None:
    v = _redis.get(f"deposit:{user_id}")
    return float(v) if v else None


def set_deposit(user_id: int, amount: float) -> None:
    _redis.set(f"deposit:{user_id}", amount)
