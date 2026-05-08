import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from analyze import analyze_tiered, fetch_price
from bot.tiers import get_tier, set_tier_start, TIER_LIMITS, ADMIN_USER_IDS
from bot.quota import check_quota, consume_quota, get_usage, check_rate_limit
from bot.policy import require_policy
from bot.formatter import format_output
from bot.menus import send_main_menu, upgrade_prompt
from bot.alerts import add_alert, get_alerts, delete_alert, ALERT_LIMITS
from bot.watchlist import add_to_watchlist, remove_from_watchlist, get_watchlist, WATCHLIST_LIMITS
from bot.referral import register_referral, get_ref_stats, consume_bonus, get_ref_code
from bot.db_users import register_user, get_all_users, get_user_count

log = logging.getLogger(__name__)


def split_message(text: str, limit: int = 4000) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.policy import has_accepted_policy, show_policy
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    if not has_accepted_policy(user.id):
        await show_policy(update)
        return
    if context.args:
        code = context.args[0]
        if code.startswith("ref_") and register_referral(user.id, code[4:]):
            await update.message.reply_text("🎁 Ты пришёл по реферальной ссылке — приятного использования!")
    await send_main_menu(update.message)


@require_policy
async def cmd_ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    stats = get_ref_stats(user_id)
    link = f"https://t.me/{bot_username}?start=ref_{stats['code']}"
    text = (
        f"👥 Реферальная программа\n\n"
        f"Твоя ссылка:\n{link}\n\n"
        f"Приглашено: {stats['invited']}\n"
        f"Оплатили: {stats['converted']}\n"
        f"Бонусных анализов: {stats['bonus']}\n\n"
        f"За каждого оплатившего — +10 анализов тебе."
    )
    await update.message.reply_text(text)


@require_policy
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_main_menu(update.message)


@require_policy
async def cmd_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tier = get_tier(user_id)
    lim = TIER_LIMITS[tier]
    used_day, _ = get_usage(user_id)

    lines = [f"💎 Ваш тариф: *{tier.capitalize()}*"]

    if tier == "trial":
        from bot.tiers import trial_days_left
        days = trial_days_left(user_id)
        lines.append(f"Осталось дней: {days}")
        lines.append(f"Анализов сегодня: {used_day}/{lim['day']}")
    elif tier in ("basic", "pro"):
        day_lim = lim["day"] or "∞"
        lines.append(f"Анализов сегодня: {used_day}/{day_lim}")
    else:
        lines.append("Безлимитный доступ")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_policy
async def cmd_set_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.tiers import set_deposit

    user_id = update.effective_user.id
    if get_tier(user_id) != "elite":
        await upgrade_prompt(update.message, "elite")
        return

    args = context.args
    if not args:
        context.user_data["waiting_deposit"] = True
        await update.message.reply_text("💰 Введите сумму депозита в USDT (только число):")
        return
    try:
        amount = float(args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Укажите положительное число.")
        return

    set_deposit(user_id, amount)
    await update.message.reply_text(f"✅ Депозит установлен: {amount:.2f} USDT")


@require_policy
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Примеры: `BTCUSDT`, `SOLUSDT ETHUSDT`\n\n"
        "/menu — меню\n"
        "/subscription — тариф и квота\n"
        "/set\\_deposit — депозит (Elite)"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.menus import TARIFFS_TEXT, tariffs_kb, main_menu_kb, upgrade_kb, UPGRADE_TEXT
    from bot.policy import has_accepted_policy
    from bot.tiers import set_deposit

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not has_accepted_policy(user_id):
        return

    if query.data.startswith("wl:"):
        if query.data == "wl:cancel":
            await query.edit_message_text("Отменено.")
            return
        if query.data.startswith("wl:confirm:"):
            symbol = query.data.split(":", 2)[2]
            tier = get_tier(user_id)
            result = add_to_watchlist(user_id, symbol, tier)
            if result == "ok":
                await query.edit_message_text(f"✅ {symbol} добавлен в вочлист.")
            elif result == "exists":
                await query.edit_message_text(f"{symbol} уже в вочлисте.")
            elif result == "limit":
                limit = WATCHLIST_LIMITS.get(tier, 0)
                await query.edit_message_text(
                    f"Достигнут лимит вочлиста ({limit} монет для {tier.capitalize()})."
                )
            return

    action = query.data.split(":")[1]

    if action == "main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_kb())

    elif action == "analyze":
        await query.edit_message_text("Отправь тикер монеты, например: BTCUSDT")

    elif action == "subscription":
        tier = get_tier(user_id)
        lim = TIER_LIMITS[tier]
        used_day, _ = get_usage(user_id)
        lines = [f"💎 Ваш тариф: {tier.capitalize()}"]
        if tier == "trial":
            from bot.tiers import trial_days_left
            lines.append(f"Осталось дней: {trial_days_left(user_id)}")
            lines.append(f"Анализов сегодня: {used_day}/{lim['day']}")
        elif tier in ("basic", "pro"):
            lines.append(f"Анализов сегодня: {used_day}/{lim['day'] or '∞'}")
        else:
            lines.append("Безлимитный доступ")
        await query.edit_message_text("\n".join(lines), reply_markup=main_menu_kb())

    elif action == "tariffs":
        await query.edit_message_text(TARIFFS_TEXT, reply_markup=tariffs_kb())

    elif action == "alerts":
        alerts = get_alerts(user_id)
        tier = get_tier(user_id)
        from bot.alerts import ALERT_LIMITS
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        limit = ALERT_LIMITS.get(tier, 0)
        lim_str = "∞" if limit == -1 else str(limit)
        if not alerts:
            text = f"🔔 Алерты (0/{lim_str})\n\nДобавить: /alert BTCUSDT >= 100000"
        else:
            lines = [f"🔔 Алерты ({len(alerts)}/{lim_str})"]
            for a in alerts:
                lines.append(f"[{a['id']}] {a['symbol']} {a['condition']} {a['value']:,.2f}")
            lines.append("\nУдалить: /delalert <id>")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=main_menu_kb())

    elif action == "tier":
        parts = query.data.split(":")
        new_tier = parts[2] if len(parts) > 2 else ""
        from bot.payments import create_invoice, PRICES
        from bot.stars import TIER_LABELS
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        label = TIER_LABELS.get(new_tier, new_tier)
        usdt = PRICES[new_tier]
        try:
            inv = create_invoice(user_id, new_tier)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💳 {usdt} USDT (Crypto)", url=inv["pay_url"])],
                [InlineKeyboardButton("« Назад", callback_data="menu:tariffs")],
            ])
            text = (
                f"{label} — 30 дней\n\n"
                f"💳 {usdt} USDT через CryptoBot\n\n"
                f"Тариф активируется автоматически после оплаты."
            )
            await query.edit_message_text(text, reply_markup=kb)
        except Exception as e:
            log.error("create_invoice error: %s", e)
            await query.edit_message_text(
                "Ошибка при создании счёта. Попробуйте позже или напишите @your_support_contact.",
                reply_markup=main_menu_kb(),
            )

    elif action == "pay":
        parts = query.data.split(":")
        method = parts[1] if len(parts) > 1 else ""
        tier = parts[2] if len(parts) > 2 else ""
        if method == "stars" and tier in ("basic", "pro", "elite"):
            from bot.stars import send_stars_invoice
            try:
                await query.edit_message_text("Счёт на оплату Stars отправлен ⬇️")
                await send_stars_invoice(user_id, tier, context)
            except Exception as e:
                log.error("Stars invoice error for user %s tier %s: %s", user_id, tier, e, exc_info=True)
                await context.bot.send_message(user_id, f"❌ Ошибка Stars: {e}")

    elif action == "deposit":
        tier = get_tier(user_id)
        if tier != "elite":
            await query.edit_message_text(
                UPGRADE_TEXT["elite"], reply_markup=upgrade_kb()
            )
            return
        context.user_data["waiting_deposit"] = True
        await query.edit_message_text("💰 Введите сумму депозита в USDT (только число):")

    elif action == "watchlist":
        from bot.menus import watchlist_kb
        parts_wl = query.data.split(":")
        if len(parts_wl) > 2 and parts_wl[2] == "add":
            context.user_data["waiting_watchlist_add"] = True
            await query.edit_message_text("Введите тикер монеты (например: BTCUSDT):")
            return
        tier = get_tier(user_id)
        wl = get_watchlist(user_id)
        limit = WATCHLIST_LIMITS.get(tier, 0)
        if not wl:
            text = f"⭐ Watchlist (0/{limit})\n\nВочлист пуст."
        else:
            lines = [f"⭐ Watchlist ({len(wl)}/{limit})"]
            for sym in wl:
                lines.append(f"• {sym}")
            lines.append("\n/wldel SYMBOL — удалить\n/wl — анализ всех")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=watchlist_kb())

    elif action == "referral":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from bot.referral import get_ref_stats
        stats = get_ref_stats(user_id)
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start=ref_{stats['code']}"
        share_url = f"https://t.me/share/url?url={link}&text=Крипто-анализ+по+9+индикаторам+—+бесплатный+старт+3+дня"
        text = (
            f"👥 Реферальная программа\n\n"
            f"Твоя ссылка:\n`{link}`\n\n"
            f"📊 Приглашено: {stats['invited']}\n"
            f"💰 Оплатили: {stats['converted']}\n"
            f"🎁 Бонусных анализов: {stats['bonus']}\n\n"
            f"За каждого оплатившего реферала — +10 анализов тебе."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Поделиться ссылкой", url=share_url)],
            [InlineKeyboardButton("« Назад", callback_data="menu:main")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "stats":
        from bot.menus import stats_period_kb
        from bot.winrate import format_user_short_report, format_user_mid_report
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text(
                "📊 Личная статистика\n\nВыберите период:",
                reply_markup=stats_period_kb(),
            )
        else:
            days = int(parts[2])
            short = format_user_short_report(user_id, days)
            mid = format_user_mid_report(user_id, days)
            await query.edit_message_text(short, reply_markup=stats_period_kb())
            await context.bot.send_message(user_id, mid)

    elif action == "help":
        text = (
            "Примеры: BTCUSDT, SOLUSDT ETHUSDT\n\n"
            "/menu — меню\n"
            "/subscription — тариф и квота\n"
            "/set_deposit — депозит (Elite)"
        )
        await query.edit_message_text(text, reply_markup=main_menu_kb())


async def _send_upgrade_limit(update, user_id: int, reason: str, lim: dict) -> None:
    from bot.menus import upgrade_limit_kb
    tier = get_tier(user_id)
    used_day, _ = get_usage(user_id)

    if reason == "trial_expired":
        text = (
            "⛔ Пробный период закончился.\n\n"
            "Выберите тариф для продолжения:"
        )
    elif reason == "day_limit":
        text = (
            f"⛔ Дневной лимит исчерпан ({lim['day']}/{lim['day']}, {tier.capitalize()}).\n\n"
            "Апгрейд открывает больше анализов в день:"
        )
    elif reason == "month_limit":
        text = (
            f"⛔ Месячный лимит исчерпан ({lim['month']}, {tier.capitalize()}).\n\n"
            "Выберите тариф с большим лимитом:"
        )
    else:
        text = "⛔ Лимит исчерпан.\n\nВыберите тариф для продолжения:"

    await update.message.reply_text(text, reply_markup=upgrade_limit_kb(tier))


@require_policy
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tier = get_tier(user_id)
    args = context.args
    if not args or len(args) < 3:
        limit = ALERT_LIMITS.get(tier, 0)
        lim_str = "∞" if limit == -1 else str(limit)
        await update.message.reply_text(
            f"Синтаксис: /alert BTCUSDT >= 100000\n"
            f"Условия: >= или <=\n"
            f"Ваш лимит алертов: {lim_str}"
        )
        return
    symbol = args[0].upper()
    condition = args[1]
    if condition not in (">=", "<="):
        await update.message.reply_text("Условие должно быть >= или <=")
        return
    try:
        value = float(args[2].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Значение должно быть числом")
        return
    alert = add_alert(user_id, symbol, condition, value, tier)
    if alert is None:
        limit = ALERT_LIMITS.get(tier, 0)
        await update.message.reply_text(
            f"Достигнут лимит алертов ({limit}) для тарифа {tier.capitalize()}.\n"
            f"Удалите старый: /alerts"
        )
        return
    await update.message.reply_text(
        f"🔔 Алерт создан [{alert['id']}]\n{symbol} {condition} {value:,.2f}"
    )


@require_policy
async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    alerts = get_alerts(user_id)
    if not alerts:
        await update.message.reply_text("Нет активных алертов.\nДобавить: /alert BTCUSDT >= 100000")
        return
    lines = ["🔔 Активные алерты:"]
    for a in alerts:
        lines.append(f"[{a['id']}] {a['symbol']} {a['condition']} {a['value']:,.2f}")
    lines.append("\nУдалить: /delalert <id>")
    await update.message.reply_text("\n".join(lines))


@require_policy
async def cmd_delalert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Укажи ID алерта: /delalert <id>\nСписок: /alerts")
        return
    if delete_alert(user_id, args[0]):
        await update.message.reply_text(f"✅ Алерт {args[0]} удалён.")
    else:
        await update.message.reply_text("Алерт не найден.")


@require_policy
async def handle_symbols(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.tiers import set_deposit

    user_id = update.effective_user.id
    raw = update.message.text.strip()

    if context.user_data.get("waiting_deposit"):
        try:
            amount = float(raw.replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите положительное число, например: 1000")
            return
        set_deposit(user_id, amount)
        context.user_data.pop("waiting_deposit", None)
        await update.message.reply_text(f"✅ Депозит установлен: {amount:.2f} USDT")
        return

    if context.user_data.get("waiting_watchlist_add"):
        context.user_data.pop("waiting_watchlist_add", None)
        symbol = raw.upper().split()[0]
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Добавить", callback_data=f"wl:confirm:{symbol}"),
            InlineKeyboardButton("❌ Отмена",   callback_data="wl:cancel"),
        ]])
        await update.message.reply_text(f"Добавить {symbol} в вочлист?", reply_markup=kb)
        return

    if not check_rate_limit(user_id):
        await update.message.reply_text("Слишком часто. Подождите 5 секунд.")
        return

    tier = get_tier(user_id)
    lim = TIER_LIMITS[tier]

    symbols = raw.upper().split()

    for symbol in symbols:
        allowed, reason = check_quota(user_id, tier, lim)
        if not allowed:
            await _send_upgrade_limit(update, user_id, reason, lim)
            return

        await update.message.reply_text(f"Анализирую {symbol}...")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, analyze_tiered, symbol)
        except Exception as e:
            log.error("Ошибка анализа %s: %s", symbol, e)
            await update.message.reply_text(f"Ошибка при анализе {symbol}: {e}")
            continue

        try:
            from bot.analysis_log import log_analysis
            log_analysis(user_id, symbol, result)
        except Exception as e:
            log.warning("analysis_log failed %s: %s", symbol, e)

        set_tier_start(user_id)
        consume_quota(user_id)

        used_day, used_month = get_usage(user_id)
        text_out = format_output(result, tier, user_id, used_day, used_month)

        for part in split_message(text_out):
            await update.message.reply_text(f"```\n{part}\n```", parse_mode="MarkdownV2")

        if tier in ("pro", "elite") and result.get("extras"):
            try:
                from bot.ai_comment import get_extras_comment
                extras_comment = await loop.run_in_executor(None, get_extras_comment, result)
                if extras_comment:
                    await update.message.reply_text(f"🔍 *Расшифровка доп. данных:*\n{extras_comment}", parse_mode="Markdown")
            except Exception as e:
                log.warning("extras_comment failed: %s", e)

        if tier == "elite":
            try:
                from bot.ai_comment import get_ai_comment
                comment = await loop.run_in_executor(None, get_ai_comment, result)
                await update.message.reply_text(f"🤖 *AI-комментарий:*\n{comment}", parse_mode="Markdown")
            except Exception as e:
                log.warning("ai_comment failed: %s", e)


@require_policy
async def cmd_wladd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Укажи тикер: /wladd BTCUSDT")
        return
    symbol = context.args[0].upper()
    tier = get_tier(user_id)
    result = add_to_watchlist(user_id, symbol, tier)
    if result == "ok":
        await update.message.reply_text(f"✅ {symbol} добавлен в Watchlist.")
    elif result == "exists":
        await update.message.reply_text(f"{symbol} уже в Watchlist.")
    else:
        limit = WATCHLIST_LIMITS.get(tier, 0)
        await update.message.reply_text(f"Лимит Watchlist ({limit}) достигнут.")


@require_policy
async def cmd_wldel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Укажи тикер: /wldel BTCUSDT")
        return
    symbol = context.args[0].upper()
    if remove_from_watchlist(user_id, symbol):
        await update.message.reply_text(f"✅ {symbol} удалён из Watchlist.")
    else:
        await update.message.reply_text(f"{symbol} не найден в Watchlist.")


@require_policy
async def cmd_wl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tier = get_tier(user_id)
    wl = get_watchlist(user_id)
    if not wl:
        await update.message.reply_text("Watchlist пуст. Добавь: /wladd BTCUSDT")
        return
    lim = TIER_LIMITS[tier]
    loop = asyncio.get_event_loop()
    await update.message.reply_text(f"Анализирую {len(wl)} монет...")
    for symbol in wl:
        ok, reason = check_quota(user_id, tier, lim)
        if not ok:
            await update.message.reply_text(f"Квота исчерпана ({reason}). Остальные пропущены.")
            break
        if not check_rate_limit(user_id):
            await asyncio.sleep(5)
        try:
            result = await loop.run_in_executor(None, analyze_tiered, symbol)
        except Exception as e:
            await update.message.reply_text(f"Ошибка {symbol}: {e}")
            continue
        try:
            from bot.analysis_log import log_analysis
            log_analysis(user_id, symbol, result)
        except Exception as e:
            log.warning("analysis_log failed %s: %s", symbol, e)
        set_tier_start(user_id)
        consume_quota(user_id)
        used_day, used_month = get_usage(user_id)
        text_out = format_output(result, tier, user_id, used_day, used_month)
        for part in split_message(text_out):
            await update.message.reply_text(f"```\n{part}\n```", parse_mode="MarkdownV2")
        if tier in ("pro", "elite") and result.get("extras"):
            try:
                from bot.ai_comment import get_extras_comment
                extras_comment = await loop.run_in_executor(None, get_extras_comment, result)
                if extras_comment:
                    await update.message.reply_text(f"🔍 *Расшифровка доп. данных:*\n{extras_comment}", parse_mode="Markdown")
            except Exception as e:
                log.warning("extras_comment failed: %s", e)
        if tier == "elite":
            try:
                from bot.ai_comment import get_ai_comment
                comment = await loop.run_in_executor(None, get_ai_comment, result)
                await update.message.reply_text(f"🤖 *AI-комментарий:*\n{comment}", parse_mode="Markdown")
            except Exception as e:
                log.warning("ai_comment failed: %s", e)


def _users_keyboard(users: list[dict]):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for u in users:
        label = f"@{u['username']}" if u["username"] else (u["first_name"] or str(u["user_id"]))
        rows.append([InlineKeyboardButton(
            f"{label[:20]}  [{u['tier']}]",
            callback_data=f"admin:pick:{u['user_id']}"
        )])
    return InlineKeyboardMarkup(rows)


def _tier_keyboard(target_uid: int):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    tiers = ["trial", "basic", "pro", "elite"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t, callback_data=f"admin:set:{target_uid}:{t}") for t in tiers],
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ])


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import time
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        return

    stats = get_user_count()
    users = get_all_users()

    header = (
        f"Пользователи: {stats['total']}\n"
        + "  ".join(f"{t}: {n}" for t, n in stats["by_tier"].items())
        + "\n\n"
        + f"{'ID':<12} {'Username':<16} {'Имя':<12} {'Тариф':<7} Дата\n"
        + "-" * 58 + "\n"
    )
    rows = []
    for u in users:
        joined = time.strftime("%d.%m", time.localtime(u["joined_at"])) if u["joined_at"] else "—"
        uname = f"@{u['username']}" if u["username"] else "—"
        name = (u["first_name"] or "—")[:11]
        rows.append(f"{u['user_id']:<12} {uname:<16} {name:<12} {u['tier']:<7} {joined}")

    text = header + "\n".join(rows)
    for part in split_message(text, limit=4000):
        await update.message.reply_text(f"```\n{part}\n```", parse_mode="MarkdownV2")

    await update.message.reply_text(
        "Выбери пользователя для смены тарифа:",
        reply_markup=_users_keyboard(users),
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.tiers import set_tier
    from bot.db_users import update_user_tier

    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_USER_IDS:
        return

    parts = query.data.split(":")

    if parts[1] == "back":
        users = get_all_users()
        await query.edit_message_text(
            "Выбери пользователя для смены тарифа:",
            reply_markup=_users_keyboard(users),
        )

    elif parts[1] == "pick":
        target_uid = int(parts[2])
        users = get_all_users()
        user = next((u for u in users if u["user_id"] == target_uid), None)
        name = f"@{user['username']}" if user and user["username"] else str(target_uid)
        current = user["tier"] if user else "?"
        await query.edit_message_text(
            f"Пользователь: {name}\nТекущий тариф: {current}\n\nВыбери новый тариф:",
            reply_markup=_tier_keyboard(target_uid),
        )

    elif parts[1] == "set":
        target_uid = int(parts[2])
        new_tier = parts[3]
        set_tier(target_uid, new_tier)
        update_user_tier(target_uid, new_tier)
        users = get_all_users()
        user = next((u for u in users if u["user_id"] == target_uid), None)
        name = f"@{user['username']}" if user and user["username"] else str(target_uid)
        await query.edit_message_text(
            f"✅ {name} → {new_tier}\n\nВыбери пользователя для смены тарифа:",
            reply_markup=_users_keyboard(users),
        )
