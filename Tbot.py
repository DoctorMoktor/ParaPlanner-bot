import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден токен бота! Установите переменную окружения BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

plans = {}

# === Список топиков, где нужно закреплять сообщение ===
TOPICS = {
    1: "ВЫЕЗДЫ",
    25461: "Фото/Видео",
    29332: "Merch 16 облаков",
    25730: "Полёты по плану",
    25458: "Болталка",
    29391: "Разрешения на полеты",
    25493: "FAQ",
    25464: "Барахолка"
}


# === Команда /getid (вспомогательная) ===
@dp.message(Command("getid"))
async def get_id(message: types.Message):
    chat_id = message.chat.id
    thread_id = getattr(message, "message_thread_id", None)
    text = f"🧩 Chat ID: `{chat_id}`"
    if thread_id:
        text += f"\n📌 Message Thread ID: `{thread_id}`"
    else:
        text += "\n📌 (Сообщение не из топика — общий чат)"

    try:
        await bot.send_message(message.from_user.id, text, parse_mode="Markdown")
    except Exception:
        await message.reply("✉️ Напиши боту в личку, чтобы он мог отправить тебе сообщение.")


# === Команда /plan ===
@dp.message(Command("plan"))
async def create_plan(message: types.Message):
    text_after_command = message.text[len("/plan"):].strip()
    args = text_after_command.split()

    if len(args) != 3:
        msg = await message.reply(
            "⚠️ Неверный формат. Используйте:\n"
            "/plan Место ДДММ ЧЧММ\n"
            "Пример: /plan Свияга 1410 1130"
        )
        await asyncio.sleep(5)
        await msg.delete()
        return

    place, date_raw, time_raw = args

    try:
        day = int(date_raw[:2])
        month = int(date_raw[2:])
        hour = int(time_raw[:2])
        minute = int(time_raw[2:])
    except Exception:
        msg = await message.reply("⚠️ Ошибка формата даты или времени. Пример: /plan Свияга 1410 1130")
        await asyncio.sleep(5)
        await msg.delete()
        return

    month_names = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    date_text = f"{day} {month_names[month]}"
    time_text = f"{hour:02d}:{minute:02d}"
    creator_name = message.from_user.full_name

    text = (
        f"🛫 **ПОДАЧА ПЛАНА ПОЛЁТОВ** 🛫\n"
        f"📍 Место: {place}\n"
        f"🗓 Дата: {date_text}\n"
        f"🕐 Время: {time_text}\n"
        f"👨‍✈️ План подаёт: {creator_name}\n\n"
        f"Отметься, если участвуешь!"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Пойду", callback_data="join")
    kb.adjust(2)

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем и закрепляем сообщение во всех топиках
    for thread_id, name in TOPICS.items():
        sent_msg = await bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=thread_id,
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )

        try:
            await bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=sent_msg.message_id,
                message_thread_id=thread_id
            )
        except Exception as e:
            print(f"⚠️ Не удалось закрепить в {name}: {e}")

        # Сохраняем данные
        plans[sent_msg.message_id] = {
            "creator_id": message.from_user.id,
            "creator_name": creator_name,
            "place": place,
            "date": date_text,
            "time": time_text,
            "participants": set()
        }

        # Таймеры:
        asyncio.create_task(close_plan_after_hour(message.chat.id, sent_msg.message_id))
        asyncio.create_task(delete_bot_message_after_hours(sent_msg.chat.id, sent_msg.message_id, 0.05))  # 1.5 часа


# === Обработка кнопок ===
@dp.callback_query(F.data == "join")
async def join_plan(callback: types.CallbackQuery):
    msg_id = callback.message.message_id
    user = callback.from_user
    if msg_id not in plans:
        await callback.answer("Этот план уже закрыт или недоступен.")
        return
    plans[msg_id]["participants"].add(user.full_name)
    await callback.answer("Вы отметились ✅")


# === Закрытие плана через 1 час ===
async def close_plan_after_hour(chat_id: int, msg_id: int):
    await asyncio.sleep(120)  # 1 час

    plan = plans.get(msg_id)
    if not plan:
        return

    text = (
        f"🟠 **ПЛАН ПОДАН** 🟠\n"
        f"📍 Место: {plan['place']}\n"
        f"🗓 Дата: {plan['date']}\n"
        f"🕐 Время: {plan['time']}\n"
        f"👨‍✈️ Создатель плана: {plan['creator_name']}\n"
        f"👥 Пилотов: {len(plan['participants'])}"
    )

    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown")
    except Exception:
        pass

    # Отправляем отчёт создателю
    try:
        await bot.send_message(
            chat_id=plan["creator_id"],
            text=f"🛫 Опрос пилотов завершён.\n"
                 f"📍 {plan['place']}, {plan['date']}, {plan['time']}\n"
                 f"👥 Участников: {len(plan['participants'])}"
        )
    except Exception:
        pass


# === Удаление сообщений бота через N часов ===
async def delete_bot_message_after_hours(chat_id: int, msg_id: int, hours: float):
    await asyncio.sleep(int(hours * 3600))
    try:
        await bot.unpin_chat_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
    if msg_id in plans:
        del plans[msg_id]


# === Запуск ===
async def main():
    print("Бот запущен ✈️")
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())
