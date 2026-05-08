from bot.redis_client import _redis

BONUS_PER_REFERRAL = 10  # бонусных анализов рефереру за каждую конверсию


def get_ref_code(user_id: int) -> str:
    return str(user_id)


def register_referral(new_user_id: int, referrer_code: str) -> bool:
    """Записать реферала при старте бота. Возвращает True если успешно."""
    try:
        referrer_id = int(referrer_code)
    except ValueError:
        return False
    if referrer_id == new_user_id:
        return False
    if _redis.exists(f"ref:by:{new_user_id}"):
        return False
    _redis.set(f"ref:by:{new_user_id}", referrer_id)
    _redis.incr(f"ref:count:{referrer_id}")
    return True


def on_tier_activated(user_id: int) -> int | None:
    """Вызывается после оплаты. Возвращает referrer_id если начислен бонус."""
    raw = _redis.get(f"ref:by:{user_id}")
    if not raw:
        return None
    referrer_id = int(raw)
    reward_key = f"ref:rewarded:{referrer_id}:{user_id}"
    if _redis.exists(reward_key):
        return None
    _redis.setex(reward_key, 365 * 86400, 1)
    _redis.incrby(f"ref:bonus:{referrer_id}", BONUS_PER_REFERRAL)
    _redis.incr(f"ref:converted:{referrer_id}")
    return referrer_id


def get_bonus(user_id: int) -> int:
    v = _redis.get(f"ref:bonus:{user_id}")
    return int(v) if v else 0


def consume_bonus(user_id: int) -> bool:
    """Списать 1 бонусный анализ. Возвращает True если был бонус."""
    if _redis.get(f"ref:bonus:{user_id}") and int(_redis.get(f"ref:bonus:{user_id}")) > 0:
        _redis.decr(f"ref:bonus:{user_id}")
        return True
    return False


def get_ref_stats(user_id: int) -> dict:
    return {
        "code": get_ref_code(user_id),
        "invited": int(_redis.get(f"ref:count:{user_id}") or 0),
        "converted": int(_redis.get(f"ref:converted:{user_id}") or 0),
        "bonus": get_bonus(user_id),
    }
