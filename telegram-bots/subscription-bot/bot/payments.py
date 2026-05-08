import os
import logging
import httpx
from bot.redis_client import _redis

log = logging.getLogger(__name__)

CRYPTOBOT_TOKEN = os.environ["CRYPTOBOT_TOKEN"]
_API = "https://pay.crypt.bot/api"

PRICES = {"basic": 19, "pro": 49, "elite": 149}
_EXPIRE_SECS = 30 * 86400  # 30 days


def _h():
    return {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}


def create_invoice(user_id: int, tier: str) -> dict:
    amount = PRICES[tier]
    payload = f"{user_id}:{tier}"
    resp = httpx.post(
        f"{_API}/createInvoice",
        headers=_h(),
        json={
            "asset": "USDT",
            "amount": str(amount),
            "payload": payload,
            "description": f"Brinky Analysis Bot — {tier.capitalize()} (30 дней)",
            "expires_in": 3600,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Cryptobot: {data}")
    invoice = data["result"]
    _redis.setex(f"invoice:{invoice['invoice_id']}", 3700, payload)
    return {"invoice_id": invoice["invoice_id"], "pay_url": invoice["pay_url"]}


def check_paid_invoices() -> list[tuple[int, str]]:
    try:
        resp = httpx.get(
            f"{_API}/getInvoices",
            headers=_h(),
            params={"status": "paid", "count": 100},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error("Cryptobot poll: %s", e)
        return []
    if not data.get("ok"):
        return []
    results = []
    for inv in data["result"].get("items", []):
        key = f"invoice:{inv['invoice_id']}"
        payload = _redis.get(key)
        if not payload:
            continue
        try:
            uid, tier = payload.split(":", 1)
        except Exception:
            continue
        _redis.delete(key)
        results.append((int(uid), tier))
    return results


def activate_tier(user_id: int, tier: str) -> None:
    _redis.setex(f"tier:{user_id}", _EXPIRE_SECS, tier)
    _redis.delete(f"tier_start:{user_id}")
    from bot.db_users import update_user_tier
    update_user_tier(user_id, tier)
