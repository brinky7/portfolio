import logging
from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes
from bot.payments import activate_tier
from bot.redis_client import _redis
from bot.tiers import ADMIN_USER_IDS

log = logging.getLogger(__name__)

# 1 USD ≈ 50 Stars (Telegram nominal rate)
STARS_PRICES = {"basic": 950, "pro": 2450, "elite": 7450}

TIER_LABELS = {"basic": "🔵 Basic", "pro": "🟣 Pro", "elite": "💎 Elite"}


async def send_stars_invoice(user_id: int, tier: str, context) -> None:
    label = TIER_LABELS.get(tier, tier.capitalize())
    stars = STARS_PRICES[tier]
    await context.bot.send_invoice(
        chat_id=user_id,
        title=f"Brinky Analysis — {label}",
        description=f"Доступ на 30 дней",
        payload=f"tier:{tier}:{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id
    try:
        _, tier, uid_str = payload.split(":")
        uid = int(uid_str)
    except Exception:
        log.error("bad Stars payload: %s", payload)
        return
    # сохраняем charge_id для возможного возврата (TTL 90 дней)
    _redis.lpush(f"stars_charges:{uid}", charge_id)
    _redis.ltrim(f"stars_charges:{uid}", 0, 4)
    _redis.expire(f"stars_charges:{uid}", 60 * 60 * 24 * 90)
    activate_tier(uid, tier)
    from bot.referral import on_tier_activated
    referrer_id = on_tier_activated(uid)
    if referrer_id:
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text="🎁 Твой реферал оплатил подписку — тебе начислено +10 анализов!",
            )
        except Exception:
            pass
    label = TIER_LABELS.get(tier, tier.capitalize())
    await update.message.reply_text(f"✅ Тариф {label} активирован на 30 дней!")


async def cmd_refund_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ: /starrefund <user_id> — возврат последней оплаты Stars."""
    caller = update.effective_user.id
    if caller not in ADMIN_USER_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /starrefund <user_id>")
        return
    try:
        target_uid = int(args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом")
        return
    charge_id = _redis.lindex(f"stars_charges:{target_uid}", 0)
    if not charge_id:
        await update.message.reply_text(f"Нет сохранённых Stars-платежей для {target_uid}")
        return
    try:
        await context.bot.refund_star_payment(
            user_id=target_uid,
            telegram_payment_charge_id=charge_id,
        )
        _redis.lrem(f"stars_charges:{target_uid}", 1, charge_id)
        await update.message.reply_text(f"✅ Возврат Stars выполнен для {target_uid}")
        log.info("Stars refund: uid=%s charge=%s", target_uid, charge_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка возврата: {e}")
        log.error("Stars refund error uid=%s: %s", target_uid, e)
