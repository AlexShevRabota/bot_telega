from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bin.config import conf_app
from bin.llm_client import llm

router = Router()


# Состояния для диалога
class ChatStates(StatesGroup):
    waiting_for_message = State()


# TODO прикрутить редис
user_histories = {}


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """
    Стартовая команда
    """
    await state.set_state(ChatStates.waiting_for_message)

    welcome_text = f"""
🤖 Привет! Я AI-бот на базе локальных нейросетей.

📚 Доступные модели:
• /coder_light - Qwen 2.5 Coder 7B (для кода, быстрая)
• /general - Llama 3.1 8B (для общих вопросов)

💡 Просто напиши мне вопрос, и я отвечу!
🔄 /reset - сбросить историю диалога
📊 /info - информация о текущей модели
"""

    await message.answer(welcome_text)


@router.message(Command("coder_light"))
async def cmd_coder_light(message: Message, state: FSMContext):
    """
    Переключение на Qwen 2.5 Coder 7B
    """
    await state.update_data(model="qwen2.5-coder:7b")
    await message.answer("⚡ Переключился на Qwen 2.5 Coder 7B (быстрая модель для кода)")


@router.message(Command("general"))
async def cmd_general(message: Message, state: FSMContext):
    """
    Переключение на Llama 3.1 8B
    """
    await state.update_data(model="llama3.1:8b")
    await message.answer("🧠 Переключился на Llama 3.1 8B (для общих вопросов)")


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """
    Сброс истории диалога
    """
    user_id = message.from_user.id
    if user_id in user_histories:
        del user_histories[user_id]
    await message.answer("🔄 История диалога сброшена")


@router.message(Command("info"))
async def cmd_info(message: Message, state: FSMContext):
    """
    Информация о текущей модели
    """
    data = await state.get_data()
    current_model = data.get("model", conf_app.DEFAULT_MODEL)

    model_info = {
        "qwen2.5-coder:7b": "⚡ Qwen 2.5 Coder 7B - быстрая модель для кода",
        "llama3.1:8b": "🧠 Llama 3.1 8B - универсальная модель для общих вопросов"
    }

    info = model_info.get(current_model, current_model)
    await message.answer(f"📊 Текущая модель:\n{info}")


@router.message(ChatStates.waiting_for_message, F.text)
async def handle_message(message: Message, state: FSMContext):
    """
    Обработка текстовых сообщений
    """
    user_id = message.from_user.id
    user_text = message.text

    # Показываем, что бот "думает"
    thinking_msg = await message.answer("🤔 Думаю...")

    # Получаем текущую модель из состояния
    data = await state.get_data()
    current_model = data.get("model", conf_app.DEFAULT_MODEL)

    # Инициализируем историю, если её нет
    if user_id not in user_histories:
        user_histories[user_id] = [
            {"role": "system", "content": "Ты — полезный AI-ассистент. Отвечай кратко и по существу."}
        ]

    # Добавляем сообщение пользователя в историю
    user_histories[user_id].append({"role": "user", "content": user_text})

    # Ограничиваем историю последними 10 сообщениями (чтобы не превысить контекст)
    if len(user_histories[user_id]) > 11:  # 1 system + 10 messages
        user_histories[user_id] = [user_histories[user_id][0]] + user_histories[user_id][-10:]

    try:
        # Запрос к LLM с историей
        response = await llm.chat_with_history(
            messages=user_histories[user_id],
            model=current_model,
            temperature=0.7
        )

        # Добавляем ответ ассистента в историю
        user_histories[user_id].append({"role": "assistant", "content": response})

        # Удаляем сообщение "Думаю..."
        await thinking_msg.delete()

        # Отвечаем пользователю
        # Если ответ длинный, разбиваем на части (Telegram ограничивает 4096 символов)
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await message.answer(response[i:i + 4000])
        else:
            await message.answer(response)

    except Exception as e:
        await thinking_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")
