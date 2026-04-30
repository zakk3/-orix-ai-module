# src/core/nlg/generator.py
# Оркестратор генерации (Шаг 2 архитектуры).
# Обновлён: PromptBuilder теперь возвращает (system, user) tuple.

from src.models.output_models import MetricCalculations
from src.core.nlg.llm_service import LLMService
from src.core.nlg.prompt_builder import PromptBuilder
from src.golden_set.golden_set_manager import GoldenSetManager


class NLGGenerator:
    """Генерирует аналитический вывод через LLM с few-shot примерами."""

    def __init__(self) -> None:
        self.llm        = LLMService()
        self.builder    = PromptBuilder()
        self.golden_set = GoldenSetManager()

    def generate(self, metric_type: str, calculations: MetricCalculations) -> str:
        """
        1. Загружаем эталоны из Golden Set (только для стиля)
        2. Собираем промпт: (system_instructions, user_content)
        3. Отправляем в LLM
        4. Возвращаем текст вывода
        """
        # Один эталон достаточно для стиля
        examples = self.golden_set.get_examples(metric_type, limit=1)

        # PromptBuilder возвращает кортеж (system, user)
        system_instructions, user_content = self.builder.build(
            metric_type=metric_type,
            calculations=calculations,
            positive_examples=examples,
        )

        verdict = self.llm.generate_with_system(system_instructions, user_content)
        return verdict