# src/models/input_models.py
#
# Pydantic-модели для валидации входных данных от Орикс.
# Орикс передаёт данные в двух форматах JSON:
#
#   Формат A — рейтинг банков (Метрика 1):
#     {"series": [{"serie":"0","label":"Мой банк","value":0.269}, ...], "avg":0.8231}
#
#   Формат B — временные ряды (Метрики 2-6):
#     {"series": [{"serie":"2022Q4","label":"2022Q4","self":166.52,"rest":215.83}, ...]}
#
# Важно: "self" — зарезервированное слово в Python, поэтому поле называется
# self_ а в JSON приходит как "self" через механизм alias в Pydantic.

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional


class OrixSeriesItem(BaseModel):
    """
    Один элемент массива series.
    Поддерживает оба формата: с полем value (рейтинг) и с self/rest (временные ряды).
    """

    model_config = ConfigDict(
        populate_by_name=True,  # разрешить задавать поля и по имени и по alias
        extra="allow"           # не ломаться если Орикс добавит новые поля
    )

    # ID элемента: "0","1","2" для рейтинга или "2022Q4","2023Q1" для временных рядов
    serie: str = Field(...)

    # Человекочитаемое название: "Мой банк", "Банк 1", "Среднее по кластеру", "2022Q4"
    label: str = Field(...)

    # Значение для Формата A (рейтинг банков по показателю BI)
    value: Optional[float] = Field(None)

    # Значение Моего банка для Формата B (временные ряды).
    # Поле называется self_ в Python, но в JSON приходит как "self".
    self_: Optional[float] = Field(None, alias="self")

    # Значение среднего по рынку для Формата B
    rest: Optional[float] = Field(None)

    @field_validator("serie", "label")
    @classmethod
    def not_empty(cls, v: str) -> str:
        """Поля serie и label не могут быть пустыми строками."""
        if not v or not v.strip():
            raise ValueError("Поле не может быть пустым")
        return v


class OrixMetricInput(BaseModel):
    """
    Полный набор входных данных для одной метрики.
    Содержит массив элементов series и опциональное среднее avg.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Массив данных по всем банкам — минимум 2 элемента (мой банк + хотя бы один другой)
    series: List[OrixSeriesItem] = Field(..., min_length=2)

    # Среднее значение по кластеру — используется в Метрике 1.
    # Если не передано — калькулятор считает сам из series.
    avg: Optional[float] = Field(None)

    @field_validator("series")
    @classmethod
    def validate_my_bank_exists(cls, v: List[OrixSeriesItem]) -> List[OrixSeriesItem]:
        """
        Проверяем что данные содержат либо:
          - элемент с label 'Мой банк' (Формат A — рейтинг)
          - элементы с полями self и rest (Формат B — временные ряды)
        Без этого расчёт невозможен.
        """
        # Ищем Мой банк по метке
        for item in v:
            if "мой банк" in item.label.lower() or "мой_банк" in item.label.lower():
                return v  # нашли — всё в порядке

        # Проверяем формат временных рядов
        has_timeseries = any(
            it.self_ is not None and it.rest is not None for it in v
        )
        if has_timeseries:
            return v  # данные в формате B — тоже хорошо

        # Ни то ни другое — ошибка
        raise ValueError(
            "В данных нет элемента 'Мой банк' и нет полей self/rest. "
            "Проверьте формат входных данных."
        )


class GenerationRequest(BaseModel):
    """
    Запрос на генерацию аналитического вывода.
    Это входная точка для pipeline — именно этот объект передаётся в process_metric().
    """

    model_config = ConfigDict(populate_by_name=True)

    # Код метрики из enums.MetricType: loss_share, recovery_level и т.д.
    metric_type: str = Field(...)

    # Отчётный период — подставляется в текст вывода
    period: str = Field(default="2025Q3")

    # Идентификатор банка — зарезервировано для будущих версий
    bank_id: str = Field(default="my_bank")

    # Входные данные в формате Орикс
    data: OrixMetricInput = Field(...)