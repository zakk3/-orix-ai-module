# src/core/pipeline.py
# Sprint 2: Шаги 2 и 3 — заглушки, будут заменены в Sprint 3

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any

from src.models.input_models import GenerationRequest
from src.models.output_models import MetricGenerationResponse, MetricCalculations
from src.models.enums import MetricType
from src.core.validation.input_validator import InputValidator
from src.core.deterministic.metric1_loss_share import Metric1Calculator


class AnalysisPipeline:

    def __init__(self) -> None:
        self.input_validator = InputValidator()
        # добавляем новые метрики сюда по мере реализации
        self.calculators = {
            MetricType.LOSS_SHARE.value: Metric1Calculator(),
        }

    def process_metric(self, request: GenerationRequest) -> MetricGenerationResponse:
        request_id = f"req_{uuid.uuid4().hex[:8]}"

        # шаг 0: валидация входных данных
        raw_dict = request.data.model_dump(by_alias=True)
        is_valid, errors = self.input_validator.validate(raw_dict)
        if not is_valid:
            raise ValueError(f"Ошибки валидации: {errors}")

        # шаг 1: детерминированные расчёты
        calculator = self.calculators.get(request.metric_type)
        if calculator is None:
            available = ", ".join(self.calculators.keys())
            raise ValueError(f"Метрика '{request.metric_type}' не поддерживается. Доступны: {available}")

        calculations = calculator.calculate(raw_dict, period=request.period)

        # шаг 2: генерация текста (заглушка до Sprint 3)
        verdict = self._verdict_placeholder(calculations, request.metric_type)

        # шаг 3: валидация вывода (заглушка до Sprint 3)
        passed, score, val_errors = self._validate_placeholder(calculations, verdict)

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

    def _verdict_placeholder(self, calculations: MetricCalculations, metric_type: str) -> str:
        # временный шаблон на основе структуры эталонов Орикс
        if metric_type != MetricType.LOSS_SHARE.value:
            return f"Вывод для метрики {metric_type} будет добавлен в Sprint 3."

        diff = calculations.difference_percent
        direction = "ниже" if calculations.is_below_average else "выше"
        threshold = calculations.deviation_threshold
        pos = calculations.position
        total = calculations.total_banks
        repr_pct = calculations.extra.get("representativeness_pct", 62)

        parts = [
            f"По итогам {calculations.period} уровень потерь в вашем банке относительно дохода "
            f"(в виде показателя BI) {threshold} {direction} среднего показателя "
            f"по другим банкам, предоставившим свои данные в ОРИКС: разница составляет {abs(diff):.1f}%."
        ]

        if threshold == "существенное" and calculations.is_below_average:
            parts.append(
                "Столь существенное отличие, скорее всего, свидетельствует о более эффективном "
                "управлении операционным риском. Вместе с тем, более низкое значение показателя "
                "может говорить о неполной регистрации потерь в вашем банке."
            )
        elif threshold == "существенное" and not calculations.is_below_average:
            parts.append(
                "Отклонение может быть результатом разовых колебаний или различий в уровне "
                "операционного дохода. Рекомендуется проанализировать динамику за предыдущие периоды."
            )

        if pos and total:
            parts.append(f"Вы находитесь на {pos} месте из {total} банков, по которым загружены данные.")

        parts.append(f"Выводы сделаны на достаточно репрезентативных данных: {repr_pct}% банков загрузили данные в ОРИКС.")

        return " ".join(parts)

    @staticmethod
    def _validate_placeholder(calculations: MetricCalculations, verdict: str) -> tuple:
        # базовые проверки: длина текста и наличие ключевых цифр
        errors = []

        if len(verdict) < 50:
            errors.append("Вердикт слишком короткий")

        diff_str = f"{abs(calculations.difference_percent):.1f}"
        if diff_str not in verdict:
            errors.append(f"Отклонение {diff_str}% не упомянуто в выводе")

        passed = len(errors) == 0
        score = 0.90 if passed else max(0.0, 0.90 - 0.1 * len(errors))
        return passed, round(score, 2), errors