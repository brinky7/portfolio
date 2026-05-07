import logging
import os
from datetime import datetime

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")

LOW_BALANCE_THRESHOLD = 100


async def run_daily_billing():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        active = await conn.fetch(
            "SELECT id, advertiser_id, daily_rate FROM products WHERE active = true"
        )
        for product in active:
            await _charge(conn, product)
    finally:
        await conn.close()


async def _charge(conn: asyncpg.Connection, product: asyncpg.Record):
    advertiser_id = product["advertiser_id"]
    rate = product["daily_rate"]

    balance = await conn.fetchval(
        "SELECT balance FROM advertisers WHERE id = $1", advertiser_id
    )

    if balance < rate:
        await conn.execute(
            "UPDATE products SET active = false WHERE id = $1", product["id"]
        )
        await _notify_paused(advertiser_id, product["id"])
        logger.info("product %d paused — insufficient balance", product["id"])
        return

    await conn.execute(
        "UPDATE advertisers SET balance = balance - $1 WHERE id = $2", rate, advertiser_id
    )
    await conn.execute(
        "INSERT INTO billing_log (product_id, amount, billed_at) VALUES ($1, $2, $3)",
        product["id"], rate, datetime.utcnow(),
    )

    if balance - rate < LOW_BALANCE_THRESHOLD:
        await _notify_low_balance(advertiser_id, balance - rate)


async def _notify_paused(advertiser_id: int, product_id: int):
    bot = Bot(token=BOT_TOKEN)
    tg_id = await _get_tg_id(advertiser_id)
    if tg_id:
        await bot.send_message(
            tg_id,
            f"⏸ Товар #{product_id} приостановлен — недостаточно средств. Пополните баланс.",
        )
    await bot.session.close()


async def _notify_low_balance(advertiser_id: int, remaining: float):
    bot = Bot(token=BOT_TOKEN)
    tg_id = await _get_tg_id(advertiser_id)
    if tg_id:
        await bot.send_message(
            tg_id,
            f"⚠️ На балансе осталось {remaining:.0f} ₽. Пополните, чтобы не прерывать показ.",
        )
    await bot.session.close()


async def _get_tg_id(advertiser_id: int) -> int | None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        return await conn.fetchval(
            "SELECT tg_id FROM advertisers WHERE id = $1", advertiser_id
        )
    finally:
        await conn.close()


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_daily_billing, CronTrigger(hour=3, minute=0))
    scheduler.start()
    logger.info("billing scheduler started")
    return scheduler
