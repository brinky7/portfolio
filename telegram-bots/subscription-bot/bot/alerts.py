import json
import uuid
import time
import logging
from bot.redis_client import _redis

log = logging.getLogger(__name__)

ALERT_LIMITS = {"trial": 1, "basic": 3, "pro": 5, "elite": 10}

_USERS_KEY = "alert_users"


def _alert_key(alert_id: str) -> str:
    return f"alert:{alert_id}"


def _user_alerts_key(user_id: int) -> str:
    return f"user_alerts:{user_id}"


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_alerts(user_id: int) -> list[dict]:
    ids = _redis.smembers(_user_alerts_key(user_id))
    result = []
    for aid in ids:
        raw = _redis.get(_alert_key(aid))
        if raw:
            result.append(json.loads(raw))
    return sorted(result, key=lambda a: a["created_at"])


def count_alerts(user_id: int) -> int:
    return _redis.scard(_user_alerts_key(user_id))


def add_alert(user_id: int, symbol: str, condition: str, value: float, tier: str) -> dict | None:
    limit = ALERT_LIMITS.get(tier, 0)
    if limit != -1 and count_alerts(user_id) >= limit:
        return None
    alert = {
        "id": str(uuid.uuid4())[:8],
        "user_id": user_id,
        "symbol": symbol.upper(),
        "condition": condition,
        "value": value,
        "created_at": int(time.time()),
    }
    _redis.set(_alert_key(alert["id"]), json.dumps(alert))
    _redis.sadd(_user_alerts_key(user_id), alert["id"])
    _redis.sadd(_USERS_KEY, user_id)
    return alert


def delete_alert(user_id: int, alert_id: str) -> bool:
    if not _redis.sismember(_user_alerts_key(user_id), alert_id):
        return False
    _redis.delete(_alert_key(alert_id))
    _redis.srem(_user_alerts_key(user_id), alert_id)
    if count_alerts(user_id) == 0:
        _redis.srem(_USERS_KEY, user_id)
    return True


def delete_all_alerts(user_id: int) -> None:
    for aid in _redis.smembers(_user_alerts_key(user_id)):
        _redis.delete(_alert_key(aid))
    _redis.delete(_user_alerts_key(user_id))
    _redis.srem(_USERS_KEY, user_id)


# ── Checker ───────────────────────────────────────────────────────────────────

def check_all_alerts(fetch_price_fn) -> list[tuple[int, dict]]:
    """Returns list of (user_id, alert) for triggered alerts, removes them."""
    triggered = []
    for uid_raw in _redis.smembers(_USERS_KEY):
        user_id = int(uid_raw)
        for alert in get_alerts(user_id):
            try:
                price = fetch_price_fn(alert["symbol"])
            except Exception as e:
                log.debug("price fetch %s: %s", alert["symbol"], e)
                continue
            cond = alert["condition"]
            val = alert["value"]
            hit = (cond == ">=" and price >= val) or (cond == "<=" and price <= val)
            if hit:
                delete_alert(user_id, alert["id"])
                triggered.append((user_id, alert, price))
    return triggered
