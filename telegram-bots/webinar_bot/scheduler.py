import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from db import get_user

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

WARMUP_OFFSETS_DAYS = [7, 3, 1]
WARMUP_OFFSETS_MINUTES = [30, 0]

WARMUP_MESSAGES = {
    7: "📋 Чек-лист для подготовки к вебинару у вас в боте. Сохраните!",
    3: "🔥 До вебинара 3 дня. Освободите время в календаре.",
    1: "⏰ Завтра вебинар! Проверьте уведомления.",
}


async def send_warmup(user_id: int, days_before: int, bot):
    text = WARMUP_MESSAGES.get(days_before)
    if text:
        await bot.send_message(user_id, text)


async def send_webinar_link(user_id: int, bot, link: str):
    await bot.send_message(user_id, f"🎬 Прямой эфир начался!\n{link}")


async def schedule_warmup_chain(user_id: int, days_left: int, webinar_dt: datetime):
    for days in WARMUP_OFFSETS_DAYS:
        if days_left > days:
            fire_at = webinar_dt - __import__("datetime").timedelta(days=days)
            scheduler.add_job(
                send_warmup,
                trigger=DateTrigger(run_date=fire_at),
                args=[user_id, days],
                id=f"warmup_{user_id}_{days}d",
                replace_existing=True,
            )
            logger.info("scheduled T-%dd for user %d", days, user_id)

    for minutes in WARMUP_OFFSETS_MINUTES:
        fire_at = webinar_dt - __import__("datetime").timedelta(minutes=minutes)
        label = f"{minutes}m" if minutes else "start"
        scheduler.add_job(
            send_webinar_link,
            trigger=DateTrigger(run_date=fire_at),
            args=[user_id],
            id=f"webinar_{user_id}_{label}",
            replace_existing=True,
        )
