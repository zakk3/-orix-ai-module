# src/models/output_models.py
# Ответ pipeline состоит из трёх блоков:
#   calculations — результаты детерминированных расчётов (шаг 1)
#   verdict      — текст от LLM (шаг 2)
#   validation   — результат авто-валидации (шаг 3)

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class MetricCalculations(BaseModel):
    metric_type: str
    period: str

    my_bank_value: float
    cluster_avg_value: float
    difference_percent: float
    is_below_average: bool

    position: Optional[int] = None
    total_banks: Optional[int] = None
    deviation_threshold: str

    # доп. поля для конкретной метрики (тренды, соотношения и т.д.)
    extra: Dict[str, Any] = Field(default_factory=dict)


class MetricGenerationResponse(BaseModel):
    request_id: str
    metric_type: str
    period: str

    calculations: MetricCalculations
    verdict: str = Field(..., min_length=50)

    quality_score: float = Field(..., ge=0.0, le=1.0)
    validation_passed: bool
    validation_errors: List[str] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=datetime.now)