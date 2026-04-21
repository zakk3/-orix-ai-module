# src/models/input_models.py
# Два формата Орикс:
#   Формат A (метрика 1): series с полем value
#   Формат B (метрики 2-6): series с полями self/rest (временные ряды)
# Важно: self — зарезервированное слово Python, поэтому используем alias

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional


class OrixSeriesItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    serie: str = Field(...)
    label: str = Field(...)
    value: Optional[float] = Field(None)
    self_: Optional[float] = Field(None, alias="self")
    rest: Optional[float] = Field(None)

    @field_validator("serie", "label")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Поле не может быть пустым")
        return v


class OrixMetricInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    series: List[OrixSeriesItem] = Field(..., min_length=2)
    avg: Optional[float] = Field(None)

    @field_validator("series")
    @classmethod
    def validate_my_bank_exists(cls, v: List[OrixSeriesItem]) -> List[OrixSeriesItem]:
        # для формата A нужен Мой банк, для формата B достаточно self/rest
        for item in v:
            if "мой банк" in item.label.lower() or "мой_банк" in item.label.lower():
                return v
        has_timeseries = any(it.self_ is not None and it.rest is not None for it in v)
        if has_timeseries:
            return v
        raise ValueError("Нет элемента 'Мой банк' и данные не в формате временных рядов")


class GenerationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    metric_type: str = Field(...)
    period: str = Field(default="2025Q3")
    bank_id: str = Field(default="my_bank")
    data: OrixMetricInput = Field(...)