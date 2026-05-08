from bot.tiers import get_deposit

BASIC_INDICATORS = {"rsi", "macd", "ema"}

_ICONS = {
    "bullish": "🟢", "oversold": "🟢", "buying": "🟢", "long": "🟢",
    "bearish": "🔴", "overbought": "🔴", "selling": "🔴", "short": "🔴",
}


def _sig_icon(sig: str) -> str:
    sig_l = sig.lower()
    for kw, icon in _ICONS.items():
        if kw in sig_l:
            return icon
    return "⚪"


def _ind_line(name: str, val: str, sig: str) -> str:
    return f"  {_sig_icon(sig)} {name:<18} {val:>10}   {sig}"


def _basic_indicators(ind: dict) -> str:
    lines = [
        f"  {'Индикатор':<18} {'Значение':>10}   Сигнал",
        f"  {'-'*50}",
        _ind_line("RSI(14)",   f"{ind['rsi']['value']:.1f}",         ind['rsi']['signal']),
        _ind_line("MACD hist", f"{ind['macd']['value']:+.4f}",        ind['macd']['signal']),
        _ind_line("EMA 20/50", f"{ind['ema']['value']:.4f}",          ind['ema']['signal']),
    ]
    return "\n".join(lines)


def _all_indicators(ind: dict) -> str:
    rows = [
        ("RSI(14)",       f"{ind['rsi']['value']:.1f}",         ind['rsi']['signal']),
        ("MACD hist",     f"{ind['macd']['value']:+.4f}",        ind['macd']['signal']),
        ("Ichimoku",      f"{ind['ichimoku']['value']:.4f}",     ind['ichimoku']['signal']),
        ("ADX(14)",       f"{ind['adx']['value']:.1f}",          ind['adx']['signal']),
        ("EMA 20/50",     f"{ind['ema']['value']:.4f}",          ind['ema']['signal']),
        ("BB width",      f"{ind['bb']['value']:.4f}",           ind['bb']['signal']),
        ("OBV",           f"{ind['obv']['value']:.0f}",          ind['obv']['signal']),
        ("CMF(20)",       f"{ind['cmf']['value']:+.4f}",         ind['cmf']['signal']),
        ("Stoch(14,3,3)", f"{ind['stoch']['value']:.1f}",        ind['stoch']['signal']),
    ]
    lines = [f"  {'Индикатор':<18} {'Значение':>10}   Сигнал", f"  {'-'*50}"]
    lines += [_ind_line(n, v, s) for n, v, s in rows]
    return "\n".join(lines)


def _entry_label(tf_data: dict) -> str:
    eff_dir = tf_data.get("effective_direction", tf_data.get("direction", "long"))
    arrow = "LONG" if eff_dir == "long" else "SHORT"
    if tf_data.get("is_suggested"):
        flat_note = ", рынок в флете" if tf_data.get("is_flat") else ""
        return f"  ⚠️  Сигнал слабый{flat_note} — на основе данных рекомендую {arrow}:"
    if tf_data.get("is_flat"):
        return f"  ⚠️  {'▲ LONG' if eff_dir == 'long' else '▼ SHORT'}  (ADX слабый — флет)"
    return f"  {'▲ LONG' if eff_dir == 'long' else '▼ SHORT'}"


def _entry_basic(tf_data: dict) -> str:
    if "entry" not in tf_data:
        return "  ⚪ Нет данных для расчёта"
    lines = [_entry_label(tf_data)]
    if tf_data.get("use_pullback") and "signal_price" in tf_data:
        lines += [
            f"  📡 Сигнал: {tf_data['signal_price']:.4f}",
            f"  🎯 Лимит:  {tf_data['entry']:.4f}  (ждём откат ~ATR, до 24ч)",
        ]
    else:
        lines.append(f"  🎯 Вход:   {tf_data['entry']:.4f}")
    lines += [
        f"  🛑 SL:     {tf_data['sl']:.4f}",
        f"  ✅ TP:     {tf_data['tp']:.4f}",
    ]
    return "\n".join(lines)


def _entry_pro(tf_data: dict) -> str:
    base = _entry_basic(tf_data)
    if "rr" in tf_data:
        base += f"\n  R:R = 1:{tf_data['rr']:.1f}"
    reasons = tf_data.get("tp_sl_reasons", [])
    if reasons:
        base += "\n  📐 " + " · ".join(reasons)
    return base


def _entry_elite(tf_data: dict, deposit: float) -> str:
    base = _entry_pro(tf_data)
    if "confidence" in tf_data and "size_pct" in tf_data:
        size_usdt = (tf_data["size_pct"] / 100) * deposit
        risk_usdt = abs(tf_data["entry"] - tf_data["sl"]) * (size_usdt / tf_data["entry"]) if tf_data.get("entry") else 0
        base += (
            f"\n  Уверенность: {tf_data['confidence']:.0%}  (confluence {tf_data.get('confluence_score', 0)}/9)"
            f"\n  💰 Размер: {size_usdt:.2f} USDT  ({tf_data['size_pct']:.1f}% от {deposit:.0f})"
            f"\n  Риск: {risk_usdt:.2f} USDT"
        )
    return base


def _section(label: str, primary_tf: str, tf_data: dict, ind_block: str, entry_block: str, confirm_lines: list[str], fallback_note: str = "") -> str:
    lines = [
        f"\n  ── {label} {'─' * max(1, 44 - len(label))}",
    ]
    if fallback_note:
        lines.append(f"  ⚠️  {fallback_note}")
    lines += [
        f"  {primary_tf}  [{tf_data.get('bullish_count', 0)}🟢 / {tf_data.get('bearish_count', 0)}🔴  confluence {tf_data.get('confluence_score', 0)}/9]",
        ind_block,
        entry_block,
    ]
    lines += confirm_lines
    return "\n".join(lines)


def _confirm_line(tf_data: dict, primary_dir: str) -> str:
    tf = tf_data["tf"]
    d = tf_data.get("direction", "neutral")
    if d == primary_dir:
        return f"  ✅ {tf} подтверждает: {d}"
    elif d != "neutral":
        return f"  ⚠️  {tf}: расхождение ({d})"
    return f"  ⚠️  {tf}: нейтрален"


def _extras_block(extras: dict) -> str:
    if not extras:
        return ""
    lines = ["\n  ── ДОПОЛНИТЕЛЬНО ────────────────────────────"]

    oi = extras.get("oi", {})
    if oi:
        sig = {"growing": "🟢", "falling": "🔴", "stable": "⚪"}.get(oi.get("signal", ""), "⚪")
        lines.append(f"  {sig} OI:        {oi['current']:,.0f}  ({oi['change_24h_pct']:+.1f}% за 24ч)  {oi['signal']}")

    fr = extras.get("funding", {})
    if fr:
        sig = {"longs_paying": "🔴", "shorts_paying": "🟢", "neutral": "⚪"}.get(fr.get("signal", ""), "⚪")
        squeeze = "  ⚠️ риск шорт-сквиза" if fr.get("squeeze_risk") else ""
        lines.append(f"  {sig} Funding:   {fr['current']:+.5f}  (avg8: {fr['avg_8']:+.5f}){squeeze}")

    liq = extras.get("liq", {})
    if liq:
        sig = {"high": "🔴", "moderate": "⚪", "low": "🟢"}.get(liq.get("activity", ""), "⚪")
        lines.append(f"  {sig} Liq акт.:  {liq['activity']}  (макс. OI-провал {liq['max_oi_drop_pct']}%)")

    cvd = extras.get("cvd", {})
    if cvd:
        sig = "🟢" if cvd.get("signal") == "bullish" else "🔴"
        lines.append(f"  {sig} CVD Δ5:    {cvd['delta_5']:+,.0f}  {cvd['signal']}")

    div = extras.get("rsi_div", {})
    if div and div.get("type") != "none":
        sig = "🟢" if div["type"] == "bullish" else "🔴"
        lines.append(f"  {sig} RSI div:   {div['type']} divergence")

    struct = extras.get("structure", {})
    if struct:
        sig = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(struct.get("signal", ""), "⚪")
        lines.append(f"  {sig} Структура: {struct['structure']}")

    poc = extras.get("poc", {})
    if poc and poc.get("poc"):
        lines.append(f"  ⚪ POC:       {poc['poc']:.4f}")

    btc = extras.get("btc_corr", {})
    if btc:
        under = "  ⚠️ слабее BTC" if btc.get("underperforming_btc") else "  ✅ сильнее BTC"
        lines.append(f"  ⚪ BTC corr:  {btc['correlation']:.2f}{under}")

    return "\n".join(lines)


def _footer_pro(used_day: int, day_limit: int) -> str:
    return f"\n  Использовано {used_day}/{day_limit} сегодня"


def format_output(result: dict, tier: str, user_id: int, used_day: int = 0, used_month: int = 0) -> str:
    symbol = result["symbol"]
    price = result["price"]
    header = f"\n{'='*52}\n  📊 {symbol}   Цена: {price:.4f} USDT\n{'='*52}"

    mid_primary_label = result["mid_term"].get("primary_label", "1D")
    mid_fallback_note = "Мало дневных данных — используется 4H+1H" if mid_primary_label == "4H" else ""

    sections = []
    for term_key, label, primary_tf, fallback_note in [
        ("short_term", "КРАТКОСРОЧНАЯ  (1–5 дней)", "1H", ""),
        ("mid_term",   "СРЕДНЕСРОЧНАЯ  (1–4 недели)", mid_primary_label, mid_fallback_note),
    ]:
        term = result[term_key]
        p = term["primary"]
        confirms = term["confirm"]
        primary_dir = p.get("direction", "neutral")

        if tier in ("trial", "basic"):
            ind_block = _basic_indicators(p["indicators"])
            entry_block = _entry_basic(p)
            confirm_lines = []
        elif tier == "pro":
            ind_block = _all_indicators(p["indicators"])
            entry_block = _entry_pro(p)
            confirm_lines = []
        else:  # elite
            ind_block = _all_indicators(p["indicators"])
            deposit = get_deposit(user_id) or 1500.0
            entry_block = _entry_elite(p, deposit)
            confirm_lines = [_confirm_line(c, primary_dir) for c in confirms]

        sections.append(_section(label, primary_tf, p, ind_block, entry_block, confirm_lines, fallback_note))

    extras_block = ""
    if tier in ("pro", "elite"):
        extras_block = _extras_block(result.get("extras", {}))

    footer = ""
    if tier == "pro":
        from bot.tiers import TIER_LIMITS
        lim = TIER_LIMITS["pro"]
        footer = _footer_pro(used_day, lim["day"])

    return header + "\n".join(sections) + extras_block + footer + f"\n{'='*52}\n"
