import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден токен бота! Установите переменную окружения BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

plans = {}
MAIN_THREAD_ID = 25730  # Только сюда публикуем план

# === Команда /plan ===
@dp.message(Command("plan"))
async def create_plan(message: types.Message):
    text_after_command = message.text[len("/plan"):].strip()
    args = text_after_command.split()

    if len(args) != 3:
        msg = await message.reply(
            "⚠️ Неверный формат. Используйте:\n"
            "/plan Место ДДММ ЧЧММ\n"
            "Пример: /plan Макулово 1410 1130"
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
        msg = await message.reply("⚠️ Ошибка формата даты или времени. Пример: 1410 1130")
        await asyncio.sleep(5)
        await msg.delete()
        return

    month_names = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    date_text = f"{day} {month_names.get(month, '???')}"
    time_text = f"{hour:02d}:{minute:02d}"
    creator_name = message.from_user.full_name

    text = (
        f"🛫 **ПОДАЧА ПЛАНА ПОЛЁТОВ** 🛫\n"
        f"Место: {place}\n"
        f"Дата: {date_text}\n"
        f"Время: {time_text}\n"
        f"План подаёт: {creator_name}\n\n"
        f"Отметься, если участвуешь!"
    )

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Пойду", callback_data="join")
    kb.adjust(2)

    chat_id = message.chat.id

    # === Создаём сообщение только в топике 25730 ===
    try:
        sent_msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown",
            message_thread_id=MAIN_THREAD_ID
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании сообщения в топике 25730: {e}")
        return

    main_msg_id = sent_msg.message_id
    plans[main_msg_id] = {
        "creator_id": message.from_user.id,
        "creator_name": creator_name,
        "place": place,
        "date": date_text,
        "time": time_text,
        "participants": set(),
        "main_thread": MAIN_THREAD_ID,
    }

    # Запускаем таймеры параллельно
    asyncio.create_task(close_plan_after_hour(chat_id, main_msg_id))
    asyncio.create_task(delete_main_message_after_2h(chat_id, main_msg_id))
    print(f"✅ План создан пользователем {creator_name}")

# === Нажатие кнопки ===
@dp.callback_query(F.data == "join")
async def join_plan(callback: types.CallbackQuery):
    msg_id = callback.message.message_id
    user = callback.from_user

    if msg_id in plans:
        plans[msg_id]["participants"].add(user.full_name)
        await callback.answer("✅ Вы отметились!")
    else:
        await callback.answer("⚠️ План уже закрыт или удалён.")

# === Закрытие через 1 час ===
async def close_plan_after_hour(chat_id: int, main_msg_id: int):
    await asyncio.sleep(3600)  # 1 час с начала опроса

    plan = plans.get(main_msg_id)
    if not plan:
        return

    # Обновляем сообщение в 25730
    text = (
        f"🟠 **ПЛАН ПОДАН** 🟠\n"
        f"Место: {plan['place']}\n"
        f"Дата: {plan['date']}\n"
        f"Время: {plan['time']}\n"
        f"План подаёт: {plan['creator_name']}\n"
        f"Пилотов: {len(plan['participants'])}"
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=main_msg_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # ✅ Отправляем отчёт создателю с именами участников
    try:
        if plan["participants"]:
            participants_list = "\n".join(f"• {name}" for name in plan["participants"])
        else:
            participants_list = "— Никто не отметился."

        report_text = (
            f"🛫 Опрос пилотов завершён.\n"
            f"📍 {plan['place']}, {plan['date']}, {plan['time']}\n"
            f"👥 Участников: {len(plan['participants'])}\n\n"
            f"{participants_list}"
        )

        await bot.send_message(chat_id=plan["creator_id"], text=report_text)
    except Exception:
        pass

# === Удаление главного поста ===
async def delete_main_message_after_2h(chat_id: int, msg_id: int):
    await asyncio.sleep(5400)  # 1.5 часа с начала опроса
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
    plans.pop(msg_id, None)
    print("Главный пост удалён из 25730")

# === Запуск ===
async def main():
    print("Бот запущен ✈️")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
