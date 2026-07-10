from openai import AsyncOpenAI
from config import conf_app
from typing import Optional


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=conf_app.OLLAMA_BASE_URL,
            api_key="ollama"
        )
        self.default_model = conf_app.DEFAULT_MODEL

    async def chat(
            self,
            message: str,
            model: Optional[str] = None,
            system_prompt: Optional[str] = None,
            temperature: float = 0.7
    ) -> str:
        """
        Асинхронный запрос к LLM
        """
        model = model or self.default_model

        messages = []

        # Добавляем системный промпт, если есть
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Добавляем сообщение пользователя
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"❌ Ошибка при запросе к модели: {str(e)}"

    async def chat_with_history(
            self,
            messages: list,
            model: Optional[str] = None,
            temperature: float = 0.7
    ) -> str:
        """
        Запрос с историей сообщений (для диалога)
        """
        model = model or self.default_model

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"❌ Ошибка при запросе к модели: {str(e)}"


# Глобальный экземпляр
llm = LLMClient()