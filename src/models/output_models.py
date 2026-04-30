# src/models/output_models.py
#
# Pydantic-модели для выходных данных pipeline.
# Ответ состоит из трёх блоков — по одному на каждый шаг архитектуры:
#
#   calculations — результаты детерминированных расчётов (Шаг 1, Python)
#   verdict      — текстовый вывод от LLM (Шаг 2, YandexGPT в Sprint 3)
#   validation   — результат авто-валидации (Шаг 3, алгоритм-оценщик)

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class MetricCalculations(BaseModel):
    """
    Результаты Шага 1 — детерминированные расчёты на Python.
    Все цифры здесь точные и проверяемые — без галлюцинаций ИИ.
    Именно эти данные LLM получает как входные при генерации текста.
    """

    # Код метрики — чтобы знать к чему относятся расчёты
    metric_type: str

    # Отчётный период — используется в тексте вывода
    period: str

    # Основные расчётные показатели
    my_bank_value: float        # значение Моего банка
    cluster_avg_value: float    # среднее по кластеру Орикс
    difference_percent: float   # отклонение в %: (мой - среднее) / среднее * 100

    # True если Мой банк ниже среднего (меньше потерь = лучше для банка)
    is_below_average: bool

    # Место в рейтинге (1 = наименьшие потери, лучший результат).
    # None если рейтинг не применим для данной метрики.
    position: Optional[int] = None
    total_banks: Optional[int] = None  # всего банков в кластере

    # Класс отклонения: "незначительное", "среднее" или "существенное"
    deviation_threshold: str

    # Дополнительные показатели — у каждой метрики свои.
    # Для Метрики 1: {"representativeness_pct": 62, "deviation_direction": "ниже"}
    # Для Метрики 2 (Sprint 3): {"my_trend": "рост", "avg_trend": "стабильный", ...}
    extra: Dict[str, Any] = Field(default_factory=dict)


class MetricGenerationResponse(BaseModel):
    """
    Полный ответ на запрос анализа.
    Содержит все три блока: расчёты, вывод и оценку качества.
    Именно этот объект возвращает метод pipeline.process_metric().
    """

    # Уникальный ID запроса — для логирования и отладки
    request_id: str

    # Код метрики и период — дублируются для удобства чтения ответа
    metric_type: str
    period: str

    # Блок 1: результаты детерминированных расчётов (всегда точные)
    calculations: MetricCalculations

    # Блок 2: текстовый аналитический вывод.
    # В Sprint 2 — шаблон. В Sprint 3 — генерирует YandexGPT.
    # Минимальная длина 50 символов — защита от пустого вывода.
    verdict: str = Field(..., min_length=50)

    # Блок 3: результаты автоматической валидации вывода.
    # quality_score от 0.0 до 1.0. Цель по ТЗ — выше 0.95 (ошибок < 5%).
    quality_score: float = Field(..., ge=0.0, le=1.0)
    validation_passed: bool                             # True если ошибок нет
    validation_errors: List[str] = Field(default_factory=list)  # список найденных проблем

    # Время генерации — для логов и истории запросов
    generated_at: datetime = Field(default_factory=datetime.now)