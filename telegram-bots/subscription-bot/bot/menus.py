from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message

TARIFFS_TEXT = (
    "💳 Тарифы\n\n"
    "Trial (3 дня, бесплатно)\n"
    "  • 3 анализа в день\n"
    "  • RSI, MACD, EMA\n\n"
    "🔵 Basic — 19 USDT/мес\n"
    "  • 5 анализов в день\n"
    "  • RSI, MACD, EMA\n\n"
    "🟣 Pro — 49 USDT/мес\n"
    "  • 15 анализов в день\n"
    "  • Все 9 индикаторов\n"
    "  • Risk:Reward\n\n"
    "💎 Elite — 149 USDT/мес\n"
    "  • Безлимит\n"
    "  • Все индикаторы + подтверждающие ТФ\n"
    "  • Уверенность сигнала\n"
    "  • Расчёт позиции (Kelly)\n"
    "  • Кастомный депозит"
)

UPGRADE_TEXT = {
    "pro": (
        "Эта функция доступна в тарифе Pro и выше.\n\n"
        "Pro открывает:\n"
        "• Все 9 индикаторов в анализе\n"
        "• Соотношение Risk:Reward\n"
        "• 15 анализов в день\n"
        "• Счётчик остатка анализов"
    ),
    "elite": (
        "Эта функция доступна только в тарифе Elite.\n\n"
        "Elite открывает:\n"
        "• Уверенность сигнала (%)\n"
        "• Расчёт размера позиции (Kelly Criterion)\n"
        "• Персональный депозит\n"
        "• Настройка параметров индикаторов\n"
        "• Подтверждающие таймфреймы (15M + 4H + 1W)\n"
        "• Безлимитные анализы"
    ),
}


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Анализ монеты", callback_data="menu:analyze"),
            InlineKeyboardButton("💎 Моя подписка", callback_data="menu:subscription"),
        ],
        [
            InlineKeyboardButton("💳 Тарифы", callback_data="menu:tariffs"),
            InlineKeyboardButton("❓ Справка", callback_data="menu:help"),
        ],
        [
            InlineKeyboardButton("🔔 Алерты", callback_data="menu:alerts"),
            InlineKeyboardButton("💰 Депозит", callback_data="menu:deposit"),
        ],
        [
            InlineKeyboardButton("⭐ Watchlist", callback_data="menu:watchlist"),
            InlineKeyboardButton("👥 Рефералы", callback_data="menu:referral"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="menu:stats"),
        ],
    ])


def stats_period_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("7 дней", callback_data="menu:stats:7"),
            InlineKeyboardButton("30 дней", callback_data="menu:stats:30"),
            InlineKeyboardButton("Всё время", callback_data="menu:stats:0"),
        ],
        [InlineKeyboardButton("📢 Канал со статистикой", url="https://t.me/your_channel")],
        [InlineKeyboardButton("« Меню", callback_data="menu:main")],
    ])


def tariffs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔵 Basic",  callback_data="menu:tier:basic"),
            InlineKeyboardButton("🟣 Pro",    callback_data="menu:tier:pro"),
            InlineKeyboardButton("💎 Elite",  callback_data="menu:tier:elite"),
        ],
        [InlineKeyboardButton("« Назад", callback_data="menu:main")],
    ])


def upgrade_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Посмотреть тарифы", callback_data="menu:tariffs"),
    ]])


async def send_main_menu(message: Message) -> None:
    await message.reply_text("Главное меню:", reply_markup=main_menu_kb())


async def upgrade_prompt(message: Message, required_tier: str) -> None:
    text = UPGRADE_TEXT.get(required_tier, "Эта функция недоступна на вашем тарифе.")
    await message.reply_text(text, reply_markup=upgrade_kb())


def watchlist_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить монету", callback_data="menu:watchlist:add")],
        [InlineKeyboardButton("« Меню", callback_data="menu:main")],
    ])


def upgrade_limit_kb(current_tier: str) -> InlineKeyboardMarkup:
    order = ["trial", "free", "basic", "pro", "elite"]
    paid = {
        "basic": ("🔵 Basic — $19", "menu:tier:basic"),
        "pro":   ("🟣 Pro — $49",   "menu:tier:pro"),
        "elite": ("💎 Elite — $149", "menu:tier:elite"),
    }
    try:
        idx = order.index(current_tier)
    except ValueError:
        idx = 0

    buttons = [
        InlineKeyboardButton(label, callback_data=cb)
        for tier, (label, cb) in paid.items()
        if order.index(tier) > idx
    ]
    rows = []
    if buttons:
        rows.append(buttons[:2])
        if len(buttons) > 2:
            rows.append(buttons[2:])
    rows.append([InlineKeyboardButton("📋 Все тарифы", callback_data="menu:tariffs")])
    return InlineKeyboardMarkup(rows)


def renewal_kb(tier: str) -> InlineKeyboardMarkup:
    labels = {
        "basic": ("🔵 Продлить Basic — $19", "menu:tier:basic"),
        "pro":   ("🟣 Продлить Pro — $49",   "menu:tier:pro"),
        "elite": ("💎 Продлить Elite — $149", "menu:tier:elite"),
    }
    upgrades = {
        "basic": ("🟣 Апгрейд на Pro — $49",   "menu:tier:pro"),
        "pro":   ("💎 Апгрейд на Elite — $149", "menu:tier:elite"),
    }
    rows = []
    if tier in labels:
        label, cb = labels[tier]
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    if tier in upgrades:
        label, cb = upgrades[tier]
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(rows)
