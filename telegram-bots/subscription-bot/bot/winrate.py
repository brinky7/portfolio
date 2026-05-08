from datetime import datetime, timedelta, timezone
from bot.analysis_log import get_stats


def _format_stats(kind: str, label: str, days: int = 7) -> str:
    now = datetime.now(timezone.utc)
    period = f"{(now - timedelta(days=days)).strftime('%d %b')} — {now.strftime('%d %b %Y')}"
    stats = get_stats(kind, days)

    if stats is None:
        return f"{label}\nПериод: {period}\n\nНет данных за этот период."

    traded = stats["traded"]
    lines = [label, f"Период: {period}", ""]

    if traded == 0:
        lines.append(f"Сигналов: {stats['total_signals']}")
        lines.append(f"⏳ Ни один не дошёл до точки входа")
    else:
        lines += [
            f"Всего сигналов: {stats['total_signals']}",
            f"✅ В прибыли: {stats['wins']} ({stats['winrate']:.1f}%)",
            f"❌ В убытке: {stats['losses']} ({100 - stats['winrate']:.1f}%)",
        ]
        if stats["no_entry"]:
            lines.append(f"⏳ Не дошли до входа: {stats['no_entry']}")
        if stats["expired"]:
            lines.append(f"⌛ Истёк срок (TP/SL не сработал): {stats['expired']}")

        if stats["top_symbols"]:
            lines += ["─────────────────────", "🔝 Топ активов:"]
            for sym, s in stats["top_symbols"]:
                wr = s["wins"] / s["total"] * 100 if s["total"] else 0
                lines.append(f"{sym} — {s['total']} сигн., {wr:.0f}% winrate")

    return "\n".join(lines)


def format_short_report(days: int = 7) -> str:
    return _format_stats("short", "📊 Краткосрочные сигналы (1H/15M)", days)


def format_mid_report(days: int = 7) -> str:
    return _format_stats("mid", "📈 Среднесрочные сигналы (1D/4H)", days)


def _format_user_stats(user_id: int, kind: str, label: str, days: int = 7) -> str:
    now = datetime.now(timezone.utc)
    if days > 0:
        period = f"{(now - timedelta(days=days)).strftime('%d %b')} — {now.strftime('%d %b %Y')}"
    else:
        period = "За всё время"
    stats = get_stats(kind, days, user_id=user_id)

    if stats is None:
        return f"{label}\nПериод: {period}\n\nНет данных за этот период."

    traded = stats["traded"]
    lines = [label, f"Период: {period}", ""]

    if traded == 0:
        lines.append(f"Сигналов: {stats['total_signals']}")
        lines.append("⏳ Ни один не дошёл до точки входа")
    else:
        lines += [
            f"Всего сигналов: {stats['total_signals']}",
            f"✅ В прибыли: {stats['wins']} ({stats['winrate']:.1f}%)",
            f"❌ В убытке: {stats['losses']} ({100 - stats['winrate']:.1f}%)",
        ]
        if stats["no_entry"]:
            lines.append(f"⏳ Не дошли до входа: {stats['no_entry']}")
        if stats["expired"]:
            lines.append(f"⌛ Истёк срок (TP/SL не сработал): {stats['expired']}")

        if stats["top_symbols"]:
            lines += ["─────────────────────", "🔝 Топ активов:"]
            for sym, s in stats["top_symbols"]:
                wr = s["wins"] / s["total"] * 100 if s["total"] else 0
                lines.append(f"{sym} — {s['total']} сигн., {wr:.0f}% winrate")

    return "\n".join(lines)


def format_user_short_report(user_id: int, days: int = 7) -> str:
    return _format_user_stats(user_id, "short", "📊 Ваши краткосрочные сигналы (1H/15M)", days)


def format_user_mid_report(user_id: int, days: int = 7) -> str:
    return _format_user_stats(user_id, "mid", "📈 Ваши среднесрочные сигналы (1D/4H)", days)


def seconds_until_next_monday_9am() -> float:
    now = datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7
    if days_ahead == 0 and now.hour >= 9:
        days_ahead = 7
    target = (now + timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    return max((target - now).total_seconds(), 60.0)


def seconds_until_next_9am() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now.hour >= 9:
        target += timedelta(days=1)
    return max((target - now).total_seconds(), 60.0)
