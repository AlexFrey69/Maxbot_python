import asyncio
import json
import logging
import os
import re

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from maxapi import Bot, Dispatcher
from maxapi.filters import F
from maxapi.types import (
    CallbackButton,
    Command,
    CommandStart,
    MessageCallback,
    MessageCreated,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

# =========================================================
# CONFIG
# =========================================================

logging.basicConfig(level=logging.INFO)

load_dotenv()

BOT_TOKEN = "f9LHodD0cOIiRXBXlK0fq37l43RGqQrTVLy8yjP4s1bHMAz-jpy3GTIBzWP0XBiixmxtx59r2czgSq2DNiKn"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

scheduler = AsyncIOScheduler()

DB_NAME = "fitness.db"

TIME_PATTERN = r"^([01]\d|2[0-3]):([0-5]\d)$"

# =========================================================
# MEMORY
# =========================================================

user_states = {}
user_workouts = {}

# =========================================================
# EXERCISES
# =========================================================

EXERCISES = {
    "stretch": "Растяжка",
    "cardio": "Кардио",
    "strength": "Силовые упражнения",
    "breathing": "Дыхательные упражнения",
    "back": "Спина и осанка",
    "legs": "Ноги",
    "abs": "Пресс",
}

# =========================================================
# DATABASE
# =========================================================


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            user_id INTEGER PRIMARY KEY,
            reminder_time TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            user_id INTEGER,
            exercises TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            completed INTEGER DEFAULT 0
        )
        """)

        await db.commit()


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(
            text="Подобрать зарядку",
            payload="select_workout"
        )
    )

    builder.row(
        CallbackButton(
            text="Создать свою зарядку",
            payload="create_workout"
        )
    )

    builder.row(
        CallbackButton(
            text="Напоминания",
            payload="reminder"
        )
    )

    builder.row(
        CallbackButton(
            text="Мой прогресс",
            payload="stats"
        )
    )

    return builder.as_markup()


def wakeup_keyboard():
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(
            text="5:00 - 7:00",
            payload="wake_early"
        )
    )

    builder.row(
        CallbackButton(
            text="8:00 - 10:00",
            payload="wake_medium"
        )
    )

    builder.row(
        CallbackButton(
            text="После 10:00",
            payload="wake_late"
        )
    )

    builder.row(
        CallbackButton(
            text="Назад",
            payload="back"
        )
    )

    return builder.as_markup()


def exercises_keyboard():
    builder = InlineKeyboardBuilder()

    for key, value in EXERCISES.items():

        builder.row(
            CallbackButton(
                text=value,
                payload=f"exercise_{key}"
            )
        )

    builder.row(
        CallbackButton(
            text="Сохранить",
            payload="save_workout"
        )
    )

    builder.row(
        CallbackButton(
            text="Назад",
            payload="back"
        )
    )

    return builder.as_markup()


# =========================================================
# REMINDERS
# =========================================================

async def send_reminder(user_id: int):

    try:

        await bot.send_message(
            chat_id=user_id,
            text="Пора сделать зарядку"
        )

    except Exception as error:
        print(error)


async def load_reminders():

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT user_id, reminder_time FROM reminders"
        ) as cursor:

            reminders = await cursor.fetchall()

            for user_id, reminder_time in reminders:

                hour, minute = map(
                    int,
                    reminder_time.split(":")
                )

                scheduler.add_job(
                    send_reminder,
                    "cron",
                    hour=hour,
                    minute=minute,
                    args=[user_id],
                    id=f"reminder_{user_id}",
                    replace_existing=True
                )


# =========================================================
# STATS
# =========================================================

async def increase_stats(user_id):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            "SELECT completed FROM stats WHERE user_id = ?",
            (user_id,)
        )

        row = await cursor.fetchone()

        if row:

            await db.execute(
                """
                UPDATE stats
                SET completed = completed + 1
                WHERE user_id = ?
                """,
                (user_id,)
            )

        else:

            await db.execute(
                """
                INSERT INTO stats (user_id, completed)
                VALUES (?, 1)
                """,
                (user_id,)
            )

        await db.commit()


# =========================================================
# START
# =========================================================

@dp.message_created(CommandStart())
@dp.message_created(Command("start"))
async def start(event: MessageCreated):

    await event.message.answer(
        (
            "Фитнес-бот\n\n"
            "Функции:\n"
            "- подбор зарядки\n"
            "- создание своей тренировки\n"
            "- напоминания\n"
            "- статистика"
        ),
        attachments=[main_keyboard()]
    )


# =========================================================
# CALLBACKS
# =========================================================

@dp.message_callback()
async def callbacks(event: MessageCallback):

    payload = event.callback.payload
    user_id = event.from_user.user_id

    # =====================================================
    # BACK
    # =====================================================

    if payload == "back":

        await event.message.answer(
            "Главное меню",
            attachments=[main_keyboard()]
        )

    # =====================================================
    # WORKOUT SELECTION
    # =====================================================

    elif payload == "select_workout":

        await event.message.answer(
            "Во сколько вы обычно просыпаетесь?",
            attachments=[wakeup_keyboard()]
        )

    elif payload == "wake_early":

        await event.message.answer(
            (
                "Рекомендуется интенсивная зарядка\n\n"
                "Длительность: 30-40 минут\n"
                "Тип:\n"
                "- кардио\n"
                "- силовые упражнения\n"
                "- растяжка"
            ),
            attachments=[main_keyboard()]
        )

    elif payload == "wake_medium":

        await event.message.answer(
            (
                "Рекомендуется средняя нагрузка\n\n"
                "Длительность: 15-25 минут\n"
                "Тип:\n"
                "- разминка\n"
                "- лёгкое кардио\n"
                "- суставная гимнастика"
            ),
            attachments=[main_keyboard()]
        )

    elif payload == "wake_late":

        await event.message.answer(
            (
                "Рекомендуется лёгкая зарядка\n\n"
                "Длительность: 10-15 минут\n"
                "Тип:\n"
                "- растяжка\n"
                "- дыхательные упражнения\n"
                "- мягкая разминка"
            ),
            attachments=[main_keyboard()]
        )

    # =====================================================
    # CREATE WORKOUT
    # =====================================================

    elif payload == "create_workout":

        user_workouts[user_id] = []

        await event.message.answer(
            "Выберите упражнения",
            attachments=[exercises_keyboard()]
        )

    elif payload.startswith("exercise_"):

        exercise = payload.replace("exercise_", "")

        if exercise not in user_workouts[user_id]:
            user_workouts[user_id].append(exercise)

        await event.message.answer(
            f"Добавлено: {EXERCISES[exercise]}",
            attachments=[exercises_keyboard()]
        )

    elif payload == "save_workout":

        exercises = user_workouts.get(user_id)

        if not exercises:

            await event.message.answer(
                "Вы не выбрали упражнения",
                attachments=[main_keyboard()]
            )

            return

        async with aiosqlite.connect(DB_NAME) as db:

            await db.execute(
                """
                INSERT INTO workouts (user_id, exercises)
                VALUES (?, ?)
                """,
                (
                    user_id,
                    json.dumps(exercises)
                )
            )

            await db.commit()

        await increase_stats(user_id)

        result = "\n".join(
            f"- {EXERCISES[item]}"
            for item in exercises
        )

        await event.message.answer(
            (
                "Тренировка сохранена\n\n"
                f"{result}"
            ),
            attachments=[main_keyboard()]
        )

    # =====================================================
    # REMINDERS
    # =====================================================

    elif payload == "reminder":

        user_states[user_id] = "waiting_time"

        await event.message.answer(
            (
                "Введите время напоминания\n\n"
                "Пример: 07:30"
            )
        )

    # =====================================================
    # STATS
    # =====================================================

    elif payload == "stats":

        async with aiosqlite.connect(DB_NAME) as db:

            cursor = await db.execute(
                """
                SELECT completed
                FROM stats
                WHERE user_id = ?
                """,
                (user_id,)
            )

            row = await cursor.fetchone()

        completed = row[0] if row else 0

        await event.message.answer(
            (
                "Статистика\n\n"
                f"Тренировок выполнено: {completed}"
            ),
            attachments=[main_keyboard()]
        )


# =========================================================
# TEXT
# =========================================================

@dp.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):

    user_id = event.from_user.user_id
    text = event.message.body.text.strip()

    state = user_states.get(user_id)

    # =====================================================
    # REMINDER TIME
    # =====================================================

    if state == "waiting_time":

        if not re.match(TIME_PATTERN, text):

            await event.message.answer(
                "Введите время в формате 07:30"
            )

            return

        async with aiosqlite.connect(DB_NAME) as db:

            await db.execute(
                """
                INSERT OR REPLACE INTO reminders (
                    user_id,
                    reminder_time
                )
                VALUES (?, ?)
                """,
                (user_id, text)
            )

            await db.commit()

        hour, minute = map(int, text.split(":"))

        scheduler.add_job(
            send_reminder,
            "cron",
            hour=hour,
            minute=minute,
            args=[user_id],
            id=f"reminder_{user_id}",
            replace_existing=True
        )

        user_states[user_id] = None

        await event.message.answer(
            f"Напоминание установлено на {text}",
            attachments=[main_keyboard()]
        )

        return

    # =====================================================
    # DEFAULT
    # =====================================================

    await event.message.answer(
        "Используйте кнопки меню",
        attachments=[main_keyboard()]
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("Bot started")

    await init_db()

    scheduler.start()

    await load_reminders()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
