# src/infrastructure/config.py
# Читает настройки из файла .env и делает их доступными во всём проекте.
# Используй: from src.infrastructure.config import config

import os
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv()


class Config:
    # Провайдер LLM: yandex или gigachat
    LLM_PROVIDER: str     = os.getenv("LLM_PROVIDER", "yandex")

    # Ключ и параметры YandexGPT
    LLM_API_KEY: str      = os.getenv("LLM_API_KEY", "")
    YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
    LLM_MODEL: str        = os.getenv("LLM_MODEL", "yandexgpt-lite")

    # Параметры генерации
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS: int    = int(os.getenv("LLM_MAX_TOKENS", "600"))
    LLM_TIMEOUT: int       = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    def validate(self) -> None:
        """Проверяем что ключи заполнены перед запуском."""
        if not self.LLM_API_KEY or self.LLM_API_KEY == "впиши_сюда_api_ключ":
            raise EnvironmentError(
                "LLM_API_KEY не задан. Создайте файл .env по образцу .env.example"
            )
        if self.LLM_PROVIDER == "yandex" and not self.YANDEX_FOLDER_ID:
            raise EnvironmentError(
                "YANDEX_FOLDER_ID не задан. Укажите его в файле .env"
            )


# Единственный экземпляр на весь проект
config = Config()