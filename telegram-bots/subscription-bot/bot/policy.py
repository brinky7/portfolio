from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.redis_client import _redis

POLICY_TEXT = (
    "📋 *Политика конфиденциальности*\n\n"
    "Используя этого бота, вы соглашаетесь с тем, что:\n\n"
    "• Мы храним ваш Telegram user\\_id в Redis для управления доступом и квотами\n"
    "• Анализы не являются инвестиционными рекомендациями\n"
    "• Торговля криптовалютой сопряжена с риском потери капитала\n"
    "• Мы не несём ответственности за ваши торговые решения\n\n"
    "Нажмите *Принять*, чтобы продолжить\\."
)


def _accept_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data="policy:accept"),
        InlineKeyboardButton("❌ Отклонить", callback_data="policy:decline"),
    ]])


def _rejected_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📖 Прочитать и принять", callback_data="policy:reread"),
    ]])


def has_accepted_policy(user_id: int) -> bool:
    return _redis.get(f"policy:{user_id}") == "1"


def accept_policy(user_id: int) -> None:
    _redis.set(f"policy:{user_id}", "1")


async def show_policy(update: Update) -> None:
    await update.message.reply_text(POLICY_TEXT, parse_mode="MarkdownV2", reply_markup=_accept_kb())


async def handle_policy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "accept":
        user_id = query.from_user.id
        from bot.onboarding import is_new_user, send_welcome
        new_user = is_new_user(user_id)
        accept_policy(user_id)
        await query.edit_message_text("✅ Принято.", parse_mode=None)
        if new_user:
            await send_welcome(query.message, user_id)
        else:
            from bot.menus import send_main_menu
            await send_main_menu(query.message)

    elif action == "decline":
        await query.edit_message_text(
            "Без принятия политики бот недоступен.",
            reply_markup=_rejected_kb(),
        )

    elif action == "reread":
        await query.edit_message_text(POLICY_TEXT, parse_mode="MarkdownV2", reply_markup=_accept_kb())


def require_policy(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not has_accepted_policy(user_id):
            await show_policy(update)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
