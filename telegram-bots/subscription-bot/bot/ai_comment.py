import os
import anthropic

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def get_ai_comment(result: dict) -> str:
    st = result["short_term"]["primary"]
    mt = result["mid_term"]["primary"]
    symbol = result["symbol"]
    price = result["price"]

    prompt = (
        f"Монета: {symbol}, цена: {price}\n"
        f"Краткосрочно ({st['tf']}): {st['direction']}, уверенность {st.get('confidence', 0):.0f}%, "
        f"бычьих сигналов {st['bullish_count']}, медвежьих {st['bearish_count']}\n"
        f"Среднесрочно ({mt['tf']}): {mt['direction']}, уверенность {mt.get('confidence', 0):.0f}%, "
        f"бычьих {mt['bullish_count']}, медвежьих {mt['bearish_count']}\n\n"
        "Дай краткий торговый комментарий на русском (2-3 предложения): "
        "ключевой вывод по сигналу и на что обратить внимание. Без лишних слов."
    )

    msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def get_extras_comment(result: dict) -> str:
    extras = result.get("extras", {})
    if not extras:
        return ""

    symbol = result["symbol"]
    parts = [f"Монета: {symbol}"]

    oi = extras.get("oi", {})
    if oi:
        parts.append(f"OI за 24ч: {oi['change_24h_pct']:+.1f}% ({oi['signal']})")

    fr = extras.get("funding", {})
    if fr:
        squeeze = ", риск шорт-сквиза" if fr.get("squeeze_risk") else ""
        parts.append(f"Funding: {fr['current']:+.5f}, тренд {fr['signal']}{squeeze}")

    liq = extras.get("liq", {})
    if liq:
        parts.append(f"Ликвидационная активность: {liq['activity']} (макс. OI-провал {liq['max_oi_drop_pct']}%)")

    cvd = extras.get("cvd", {})
    if cvd:
        parts.append(f"CVD (покупки - продажи за 5 свечей): {cvd['delta_5']:+,.0f} ({cvd['signal']})")

    div = extras.get("rsi_div", {})
    if div and div.get("type") != "none":
        parts.append(f"RSI дивергенция: {div['type']}")

    struct = extras.get("structure", {})
    if struct:
        parts.append(f"Структура рынка: {struct['structure']}")

    poc = extras.get("poc", {})
    if poc and poc.get("poc"):
        parts.append(f"POC (уровень макс. объёма): {poc['poc']:.4f}")

    btc = extras.get("btc_corr", {})
    if btc:
        rel = "слабее BTC" if btc.get("underperforming_btc") else "сильнее BTC"
        parts.append(f"Корреляция с BTC: {btc['correlation']:.2f}, монета {rel}")

    data_str = "\n".join(parts)

    prompt = (
        f"{data_str}\n\n"
        "Объясни этот дополнительный блок данных простым языком на русском (3-4 предложения): "
        "что означает каждый показатель, как они вместе влияют на торговое решение, "
        "и на что трейдеру обратить особое внимание прямо сейчас. Без технического жаргона."
    )

    msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
