from bot.redis_client import _redis

WATCHLIST_LIMITS = {"trial": 1, "basic": 2, "pro": 3, "elite": 5}

def _key(user_id: int) -> str:
    return f"watchlist:{user_id}"

def get_watchlist(user_id: int) -> list[str]:
    return [s.decode() if isinstance(s, bytes) else s for s in _redis.lrange(_key(user_id), 0, -1)]

def add_to_watchlist(user_id: int, symbol: str, tier: str) -> str:
    limit = WATCHLIST_LIMITS.get(tier, 0)
    wl = get_watchlist(user_id)
    if symbol.upper() in wl:
        return "exists"
    if len(wl) >= limit:
        return "limit"
    _redis.rpush(_key(user_id), symbol.upper())
    return "ok"

def remove_from_watchlist(user_id: int, symbol: str) -> bool:
    removed = _redis.lrem(_key(user_id), 0, symbol.upper())
    return removed > 0
