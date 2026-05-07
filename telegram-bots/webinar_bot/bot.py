import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from db import get_user, save_registration
from integrations import register_in_bizon, send_to_mindbox
from scheduler import schedule_warmup_chain

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
WEBINAR_DATE = datetime.fromisoformat(os.getenv("WEBINAR_DATE"))


class Reg(StatesGroup):
    waiting_email = State()
    waiting_phone = State()


def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def start(message: Message, state: FSMContext):
    existing = await get_user(message.from_user.id)
    if existing:
        await message.answer("Вы уже зарегистрированы. Ждём вас на вебинаре!")
        return

    await message.answer("Введите ваш email:")
    await state.set_state(Reg.waiting_email)


async def got_email(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        await message.answer("Формат не тот. Попробуйте ещё раз:")
        return

    await state.update_data(email=email)
    await message.answer("Теперь номер телефона:", reply_markup=phone_keyboard())
    await state.set_state(Reg.waiting_phone)


async def got_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    data = await state.get_data()

    user_id = message.from_user.id
    username = message.from_user.username
    await save_registration(user_id, username, data["email"], phone, source="tg")

    await send_to_mindbox(data["email"], phone)
    await register_in_bizon(user_id, data["email"], phone, source="tg")

    days_left = (WEBINAR_DATE - datetime.now()).days
    await schedule_warmup_chain(user_id, days_left, WEBINAR_DATE)

    await message.answer(
        "Готово! Вы зарегистрированы.\n"
        f"Вебинар — {WEBINAR_DATE.strftime('%d.%m в %H:%M')}.\n"
        "Напомним заранее.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.clear()


async def tilda_webhook(user_id: int, email: str, phone: str):
    await save_registration(user_id, None, email, phone, source="tilda")
    await send_to_mindbox(email, phone)
    await register_in_bizon(user_id, email, phone, source="tilda")

    days_left = (WEBINAR_DATE - datetime.now()).days
    await schedule_warmup_chain(user_id, days_left, WEBINAR_DATE)


def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, CommandStart())
    dp.message.register(got_email, Reg.waiting_email)
    dp.message.register(got_phone, Reg.waiting_phone, F.contact | F.text)

    dp.run_polling(bot)


if __name__ == "__main__":
    main()
