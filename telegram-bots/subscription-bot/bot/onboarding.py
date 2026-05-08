from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.redis_client import _redis


def is_new_user(user_id: int) -> bool:
    return not _redis.exists(f"onboarded:{user_id}")


def mark_onboarded(user_id: int) -> None:
    _redis.set(f"onboarded:{user_id}", "1")


WELCOME_TEXT = (
    "👋 Добро пожаловать в Brinky Analysis!\n\n"
    "Я делаю технический анализ крипты за секунды:\n"
    "• RSI, MACD, EMA, Bollinger, Ichimoku и ещё 4 индикатора\n"
    "• Краткосрочный и среднесрочный прогноз\n"
    "• Entry / Stop-Loss / Take-Profit уровни\n"
    "• Risk:Reward соотношение\n\n"
    "📅 Пробный период: 3 дня, 3 анализа в день — бесплатно.\n\n"
    "Отправьте тикер монеты чтобы попробовать:\n"
    "BTCUSDT   ETHUSDT   SOLUSDT"
)


def onboarding_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Тарифы", callback_data="menu:tariffs")],
        [InlineKeyboardButton("📋 Главное меню", callback_data="menu:main")],
    ])


async def send_welcome(message: Message, user_id: int) -> None:
    mark_onboarded(user_id)
    await message.reply_text(WELCOME_TEXT, reply_markup=onboarding_kb())
