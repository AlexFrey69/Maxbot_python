import asyncio
import random
import sqlite3

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, ButtonsPayload, MessageButton

TOKEN = "f9LHodD0cOIiRXBXlK0fq37l43RGqQrTVLy8yjP4s1bHMAz-jpy3GTIBzWP0XBiixmxtx59r2czgSq2DNiKn"

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================
# DB
# =========================

db = sqlite3.connect("fitness_bot.db")
cursor = db.cursor()

cursor.execute("DROP TABLE IF EXISTS workouts")

cursor.execute("""
CREATE TABLE workouts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    exercises TEXT
)
""")

db.commit()

# =========================
# DATA
# =========================

EXERCISES = [
    "Прыжки — 30 сек",
    "Приседания — 20 раз",
    "Планка — 40 сек",
    "Отжимания — 15 раз",
    "Выпады — 20 раз",
    "Бег на месте — 1 мин",
    "Растяжка — 1 мин",
    "Скручивания — 20 раз",
]

states = {}
temp_data = {}

# =========================
# KEYBOARDS
# =========================

def main_menu():
    return ButtonsPayload(
        buttons=[
            [MessageButton(text="Подобрать зарядку")],
            [MessageButton(text="Создать свою зарядку")],
            [MessageButton(text="Мои тренировки")],
            [MessageButton(text="Изменить тренировку")],
            [MessageButton(text="Удалить тренировку")],
            [MessageButton(text="Мой прогресс")]
        ]
    ).pack()


def workout_menu():
    return ButtonsPayload(
        buttons=[
            [MessageButton(text="Раннее утро")],
            [MessageButton(text="Утро")],
            [MessageButton(text="Позднее утро")],
            [MessageButton(text="Назад")]
        ]
    ).pack()

# =========================
# WORKOUT LOGIC
# =========================

def generate_workout_by_count(count: int):
    selected = random.sample(EXERCISES, min(count, len(EXERCISES)))

    text = "Зарядка:\n\n"
    for i, ex in enumerate(selected, 1):
        text += f"{i}. {ex}\n"
    return text


def workout_by_time(label: str):
    if label == "Раннее утро":
        return generate_workout_by_count(6)
    elif label == "Утро":
        return generate_workout_by_count(4)
    elif label == "Позднее утро":
        return generate_workout_by_count(2)
    return "Ошибка выбора"

# =========================
# HANDLER
# =========================

@dp.message_created()
async def handler(event: MessageCreated):

    user_id = event.from_user.user_id
    text = event.message.body.text

    # START
    if text.lower() in ["/start", "start", "главное меню"]:
        await event.message.answer("Главное меню", attachments=[main_menu()])

    # WORKOUT MENU
    elif text == "Подобрать зарядку":
        await event.message.answer("Выберите время:", attachments=[workout_menu()])

    elif text in ["Раннее утро", "Утро", "Позднее утро"]:
        await event.message.answer(workout_by_time(text), attachments=[main_menu()])

    # CREATE
    elif text == "Создать свою зарядку":
        states[user_id] = "create_title"
        await event.message.answer("Введите название")

    elif states.get(user_id) == "create_title":
        temp_data[user_id] = {"title": text}
        states[user_id] = "create_exercises"
        await event.message.answer("Введите упражнения через запятую")

    elif states.get(user_id) == "create_exercises":
        cursor.execute(
            "INSERT INTO workouts(user_id, title, exercises) VALUES (?, ?, ?)",
            (user_id, temp_data[user_id]["title"], text)
        )
        db.commit()

        states[user_id] = None
        await event.message.answer("Сохранено", attachments=[main_menu()])

    # MY WORKOUTS
    elif text == "Мои тренировки":
        cursor.execute("SELECT id, title, exercises FROM workouts WHERE user_id=?", (user_id,))
        data = cursor.fetchall()

        if not data:
            await event.message.answer("Нет тренировок", attachments=[main_menu()])
            return

        msg = "Мои тренировки:\n\n"
        for i, (wid, t, e) in enumerate(data, 1):
            msg += f"{i}. {t}\n{e}\n\n"

        await event.message.answer(msg, attachments=[main_menu()])

    # DELETE
    elif text == "Удалить тренировку":
        cursor.execute("SELECT id, title FROM workouts WHERE user_id=?", (user_id,))
        data = cursor.fetchall()

        if not data:
            await event.message.answer("Нет тренировок", attachments=[main_menu()])
            return

        temp_data[user_id] = {"delete_list": data}
        states[user_id] = "delete_select"

        msg = "Выберите номер для удаления:\n\n"
        for i, (_, title) in enumerate(data, 1):
            msg += f"{i}. {title}\n"

        await event.message.answer(msg)

    elif states.get(user_id) == "delete_select":
        try:
            index = int(text) - 1
            data = temp_data[user_id]["delete_list"]
            workout_id = data[index][0]

            cursor.execute("DELETE FROM workouts WHERE id=?", (workout_id,))
            db.commit()

            states[user_id] = None
            temp_data.pop(user_id, None)

            await event.message.answer("Удалено", attachments=[main_menu()])
        except:
            await event.message.answer("Ошибка выбора")

    # EDIT WORKOUT
    elif text == "Изменить тренировку":
        cursor.execute("SELECT id, title FROM workouts WHERE user_id=?", (user_id,))
        data = cursor.fetchall()

        if not data:
            await event.message.answer("Нет тренировок", attachments=[main_menu()])
            return

        temp_data[user_id] = {"edit_list": data}
        states[user_id] = "edit_select"

        msg = "Выберите номер тренировки для изменения:\n\n"
        for i, (_, title) in enumerate(data, 1):
            msg += f"{i}. {title}\n"

        await event.message.answer(msg)

    elif states.get(user_id) == "edit_select":
        try:
            index = int(text) - 1
            data = temp_data[user_id]["edit_list"]

            workout_id = data[index][0]
            temp_data[user_id]["edit_id"] = workout_id

            states[user_id] = "edit_title"
            await event.message.answer("Введите новое название")
        except:
            await event.message.answer("Ошибка выбора")

    elif states.get(user_id) == "edit_title":
        temp_data[user_id]["new_title"] = text
        states[user_id] = "edit_exercises"
        await event.message.answer("Введите новые упражнения через запятую")

    elif states.get(user_id) == "edit_exercises":
        cursor.execute("""
            UPDATE workouts
            SET title=?, exercises=?
            WHERE id=?
        """, (
            temp_data[user_id]["new_title"],
            text,
            temp_data[user_id]["edit_id"]
        ))

        db.commit()

        states[user_id] = None
        temp_data.pop(user_id, None)

        await event.message.answer("Изменено", attachments=[main_menu()])

    # PROGRESS
    elif text == "Мой прогресс":
        cursor.execute("SELECT COUNT(*) FROM workouts WHERE user_id=?", (user_id,))
        count = cursor.fetchone()[0]

        await event.message.answer(
            f"Тренировок: {count}",
            attachments=[main_menu()]
        )

    elif text == "Назад":
        await event.message.answer("Меню", attachments=[main_menu()])


# =========================
# START
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
