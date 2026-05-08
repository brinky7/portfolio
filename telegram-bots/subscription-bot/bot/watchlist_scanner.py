import time
import logging

from bot.redis_client import _redis

log = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.80
_DEDUP_TTL = 86400  # 24 часа


def get_last_signal_time(user_id: int, symbol: str) -> int | None:
    val = _redis.get(f"wl_sent:{user_id}:{symbol}")
    if val:
        return int(val)
    return None


def mark_signal_sent(user_id: int, symbol: str) -> None:
    _redis.setex(f"wl_sent:{user_id}:{symbol}", _DEDUP_TTL, int(time.time()))


def scan_user_watchlist(user_id: int, analyze_fn) -> list[dict]:
    from bot.watchlist import get_watchlist
    wl = get_watchlist(user_id)
    results = []
    for symbol in wl:
        try:
            time.sleep(0.3)
            result = analyze_fn(symbol)
            signal = result.get("short_term", {}).get("primary", {})
            confidence = signal.get("confidence", 0.0)
            direction = signal.get("effective_direction") or signal.get("direction", "neutral")
            entry = signal.get("entry")
            sl = signal.get("sl")
            tp = signal.get("tp")
            tf = signal.get("tf", "1H")

            if confidence < CONFIDENCE_THRESHOLD:
                continue
            if direction == "neutral" or not entry or not sl or not tp:
                continue
            if get_last_signal_time(user_id, symbol) is not None:
                continue

            mark_signal_sent(user_id, symbol)
            results.append({
                "symbol": symbol,
                "direction": direction,
                "timeframe": tf,
                "confidence": confidence,
                "entry": entry,
                "tp": tp,
                "sl": sl,
            })
        except Exception as e:
            log.warning("watchlist scan error %s/%s: %s", user_id, symbol, e)
    return results
