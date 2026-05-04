# src/core/pipeline.py
# Главный оркестратор. Поток не изменён:
# InputValidator → Metric1Calculator → NLGGenerator → Evaluator → Response

from __future__ import annotations

import uuid
from datetime import datetime

from src.models.input_models import GenerationRequest
from src.models.output_models import MetricGenerationResponse
from src.models.enums import MetricType
from src.core.validation.input_validator import InputValidator
from src.core.validation.evaluator import Evaluator
from src.core.deterministic.metric1_loss_share import Metric1Calculator
from src.core.deterministic.metric2_direct_losses import Metric2Calculator
from src.core.nlg.generator import NLGGenerator


class AnalysisPipeline:

    def __init__(self) -> None:
        self.input_validator = InputValidator()
        # добавляем новые метрики сюда по мере реализации
        self.calculators = {
            MetricType.LOSS_SHARE.value: Metric1Calculator(),
            MetricType.DIRECT_LOSSES_DYNAMICS.value: Metric2Calculator(),
        }
        self.generator = NLGGenerator()
        self.evaluator = Evaluator()

    def process_metric(self, request: GenerationRequest) -> MetricGenerationResponse:
        """Полный цикл: валидация → расчёты → LLM → оценка качества."""
        request_id = f"req_{uuid.uuid4().hex[:8]}"

        # by_alias=True чтобы self_ вернулось как "self" в словаре
        raw_dict = request.data.model_dump(by_alias=True)

        # Шаг 0: валидация входных данных
        is_valid, errors = self.input_validator.validate(raw_dict)
        if not is_valid:
            raise ValueError(f"Ошибки валидации: {errors}")

        # Шаг 1: детерминированные расчёты — deviation_level и magnitude_label
        calculator = self.calculators.get(request.metric_type)
        if calculator is None:
            available = ", ".join(self.calculators.keys())
            raise ValueError(
                f"Метрика '{request.metric_type}' не поддерживается. "
                f"Доступны: {available}"
            )
        calculations = calculator.calculate(raw_dict, period=request.period)

        # Шаг 2: генерация текста через YandexGPT + few-shot стиль
        try:
            verdict = self.generator.generate(request.metric_type, calculations)
        except (TimeoutError, RuntimeError) as e:
            raise RuntimeError(
                f"Ошибка при генерации вывода: {e}. "
                "Проверьте API-ключ в файле .env"
            ) from e

        # Шаг 3: автоматическая валидация с anti-hallucination
        passed, score, val_errors = self.evaluator.evaluate(verdict, calculations)

        return MetricGenerationResponse(
            request_id=request_id,
            metric_type=request.metric_type,
            period=request.period,
            calculations=calculations,
            verdict=verdict,
            quality_score=score,
            validation_passed=passed,
            validation_errors=val_errors,
            generated_at=datetime.now(),
        )