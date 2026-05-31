# src/core/pipeline.py
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
from src.core.deterministic.metric3_loss_buckets import Metric3Calculator
from src.core.deterministic.metric4_recovery import Metric4Calculator
from src.core.deterministic.metric5_concentration import Metric5Calculator
from src.core.nlg.generator import NLGGenerator


class AnalysisPipeline:

    def __init__(self) -> None:
        self.input_validator = InputValidator()
        self.calculators = {
            MetricType.LOSS_SHARE.value: Metric1Calculator(),
            MetricType.DIRECT_LOSSES_DYNAMICS.value: Metric2Calculator(),
            MetricType.LOSS_BUCKETS.value: Metric3Calculator(),
            MetricType.RECOVERY_LEVEL.value: Metric4Calculator(),
            MetricType.CONCENTRATION.value: Metric5Calculator(),
        }
        self.generator = NLGGenerator()
        self.evaluator = Evaluator()

    def process_metric(self, request: GenerationRequest) -> MetricGenerationResponse:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        raw_dict = request.data.model_dump(by_alias=True)
        is_valid, errors = self.input_validator.validate(raw_dict)
        if not is_valid:
            raise ValueError(f"Errors: {errors}")
        calculator = self.calculators.get(request.metric_type)
        if calculator is None:
            available = ', '.join(self.calculators.keys())
            raise ValueError(f"Metric not supported. Available: {available}")
        calculations = calculator.calculate(raw_dict, period=request.period)
        try:
            verdict = self.generator.generate(request.metric_type, calculations)
        except (TimeoutError, RuntimeError) as e:
            raise RuntimeError(f"Generation error: {e}") from e
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
