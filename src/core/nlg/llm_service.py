# src/core/nlg/llm_service.py
# Обёртка над YandexGPT API.
# Обновлён: добавлен метод generate_with_system(system, user)
# для раздельной передачи system instructions и user content.
# temperature=0.0 — детерминированные ответы (curator feedback).

import requests
from src.infrastructure.config import config


class LLMService:
    """Отправляет промпт в LLM и возвращает текстовый ответ."""

    def generate_with_system(self, system: str, user: str) -> str:
        """
        Основной метод. Передаёт system instructions и user content отдельно.
        system — инструкции и ограничения для LLM
        user   — данные и задание
        """
        config.validate()
        if config.LLM_PROVIDER == "yandex":
            return self._call_yandex(system, user)
        raise ValueError(f"Неизвестный LLM_PROVIDER: '{config.LLM_PROVIDER}'")

    def generate(self, prompt: str) -> str:
        """Упрощённый метод — весь текст как user message."""
        return self.generate_with_system("", prompt)

    def _call_yandex(self, system: str, user: str) -> str:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "text": system})
        messages.append({"role": "user", "text": user})

        body = {
            "modelUri": f"gpt://{config.YANDEX_FOLDER_ID}/{config.LLM_MODEL}",
            "completionOptions": {
                "stream": False,
                # temperature=0.0 — детерминированные ответы (curator feedback)
                "temperature": 0.0,
                "maxTokens": config.LLM_MAX_TOKENS,
            },
            "messages": messages,
        }

        try:
            response = requests.post(url, headers=headers, json=body,
                                     timeout=config.LLM_TIMEOUT)
            response.raise_for_status()
        except requests.Timeout:
            raise TimeoutError(
                f"YandexGPT не ответил за {config.LLM_TIMEOUT} секунд."
            )
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Ошибка YandexGPT API: {e.response.status_code} — {e.response.text}"
            )

        data = response.json()
        try:
            text = data["result"]["alternatives"][0]["message"]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Неожиданный формат ответа: {data}") from e

        return text.strip()