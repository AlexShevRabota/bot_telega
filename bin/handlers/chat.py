import asyncio
import logging
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bin.config import conf_app
from bin.llm_client import llm

logger = logging.getLogger(__name__)
router = Router()

# --- Конфигурация моделей (единый источник правды) ---
MODELS = {
    "coder_light": {
        "id": "qwen2.5-coder:7b",
        "label": "⚡ Qwen 2.5 Coder 7B",
        "description": "быстрая модель для кода",
    },
    "general": {
        "id": "llama3.1:8b",
        "label": "🧠 Llama 3.1 8B",
        "description": "универсальная модель для общих вопросов",
    },
}
MODEL_BY_ID = {m["id"]: m for m in MODELS.values()}

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Ты — полезный AI-ассистент. Отвечай кратко и по существу.",
}

MAX_HISTORY_PAIRS = 5  # храним system + последние N пар user/assistant
TELEGRAM_MSG_LIMIT = 4000


# TODO: заменить на Redis с тем же интерфейсом (get/append/reset)
class HistoryStore:
    """In-memory хранилище истории диалогов с блокировкой на пользователя,
    чтобы конкурентные сообщения от одного user_id не портили друг другу контекст."""

    def __init__(self):
        self._histories: dict[int, list[dict]] = {}
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock_for(self, user_id: int) -> asyncio.Lock:
        return self._locks[user_id]

    def get(self, user_id: int) -> list[dict]:
        if user_id not in self._histories:
            self._histories[user_id] = [dict(SYSTEM_PROMPT)]
        return self._histories[user_id]

    def append(self, user_id: int, role: str, content: str) -> None:
        history = self.get(user_id)
        history.append({"role": role, "content": content})
        self._trim(user_id)

    def _trim(self, user_id: int) -> None:
        history = self._histories[user_id]
        max_len = 1 + MAX_HISTORY_PAIRS * 2  # system + N пар
        if len(history) > max_len:
            # обрезаем строго парами, чтобы не разорвать user/assistant
            tail_pairs = (max_len - 1) // 2
            self._histories[user_id] = [history[0]] + history[-tail_pairs * 2:]

    def reset(self, user_id: int) -> None:
        self._histories.pop(user_id, None)


history_store = HistoryStore()


def _model_info_text(model_id: str) -> str:
    meta = MODEL_BY_ID.get(model_id)
    if meta:
        return f"{meta['label']} - {meta['description']}"
    return model_id


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Стартовая команда"""
    welcome_text = (
        "🤖 Привет! Я AI-бот на базе локальных нейросетей.\n\n"
        "📚 Доступные модели:\n"
        "• /coder_light - Qwen 2.5 Coder 7B (для кода, быстрая)\n"
        "• /general - Llama 3.1 8B (для общих вопросов)\n\n"
        "💡 Просто напиши мне вопрос, и я отвечу!\n"
        "🔄 /reset - сбросить историю диалога\n"
        "📊 /info - информация о текущей модели"
    )
    await message.answer(welcome_text)


@router.message(Command("coder_light"))
async def cmd_coder_light(message: Message, state: FSMContext):
    """Переключение на Qwen 2.5 Coder 7B"""
    await state.update_data(model=MODELS["coder_light"]["id"])
    await message.answer(f"{MODELS['coder_light']['label']} — модель переключена")


@router.message(Command("general"))
async def cmd_general(message: Message, state: FSMContext):
    """Переключение на Llama 3.1 8B"""
    await state.update_data(model=MODELS["general"]["id"])
    await message.answer(f"{MODELS['general']['label']} — модель переключена")


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Сброс истории диалога"""
    history_store.reset(message.from_user.id)
    await message.answer("🔄 История диалога сброшена")


@router.message(Command("info"))
async def cmd_info(message: Message, state: FSMContext):
    """Информация о текущей модели"""
    data = await state.get_data()
    current_model = data.get("model", conf_app.DEFAULT_MODEL)
    await message.answer(f"📊 Текущая модель:\n{_model_info_text(current_model)}")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_message(message: Message, state: FSMContext):
    """Обработка текстовых сообщений (не зависит от FSM-состояния —
    работает даже если пользователь не вызывал /start)."""
    user_id = message.from_user.id
    user_text = message.text

    data = await state.get_data()
    current_model = data.get("model", conf_app.DEFAULT_MODEL)

    async with history_store.lock_for(user_id):
        await message.bot.send_chat_action(message.chat.id, "typing")
        thinking_msg = await message.answer("🤔 Думаю...")

        history_store.append(user_id, "user", user_text)
        messages = history_store.get(user_id)

        try:
            response = await llm.chat_with_history(
                messages=messages,
                model=current_model,
                temperature=0.7,
            )
            history_store.append(user_id, "assistant", response)

            await thinking_msg.delete()

            if len(response) > TELEGRAM_MSG_LIMIT:
                for i in range(0, len(response), TELEGRAM_MSG_LIMIT):
                    await message.answer(response[i:i + TELEGRAM_MSG_LIMIT])
            else:
                await message.answer(response)

        except Exception:
            logger.exception("LLM request failed for user_id=%s, model=%s", user_id, current_model)
            # откатываем незавершённый user-запрос, чтобы не засорять историю
            history = history_store.get(user_id)
            if history and history[-1]["role"] == "user":
                history.pop()
            await thinking_msg.edit_text(
                "❌ Не удалось получить ответ от модели. Попробуйте ещё раз чуть позже."
            )