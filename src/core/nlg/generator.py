# src/core/nlg/generator.py
# Оркестратор генерации (Шаг 2 архитектуры).
# Обновлён: PromptBuilder теперь возвращает (system, user) tuple.
# Обновлён: для метрик со сценариями (например, direct_losses_dynamics)
# эталон стиля подбирается ПО ТОЙ ЖЕ категории сценария, что и текущий
# расчёт — а не один и тот же эталон для всех случаев.

from src.models.output_models import MetricCalculations
from src.core.nlg.llm_service import LLMService
from src.core.nlg.prompt_builder import PromptBuilder
from src.golden_set.golden_set_manager import GoldenSetManager

# Какое поле в calculations.extra определяет «категорию сценария» для
# метрики — используется, чтобы подобрать эталон ТОЙ ЖЕ категории.
# Метрики без записи в этом маппинге используют старое поведение
# (детерминированно первые examples из файла).
SCENARIO_MATCH_FIELD = {
    "direct_losses_dynamics": "divergence_label",
}


class NLGGenerator:
    """Генерирует аналитический вывод через LLM с few-shot примерами."""

    def __init__(self) -> None:
        self.llm        = LLMService()
        self.builder    = PromptBuilder()
        self.golden_set = GoldenSetManager()

    def generate(self, metric_type: str, calculations: MetricCalculations) -> str:
        """
        1. Загружаем эталон из Golden Set (только для стиля) —
           для метрик со сценариями подбираем эталон ТОЙ ЖЕ категории
        2. Собираем промпт: (system_instructions, user_content)
        3. Отправляем в LLM
        4. Возвращаем текст вывода
        """
        match_field = SCENARIO_MATCH_FIELD.get(metric_type)
        if match_field:
            match_value = calculations.extra.get(match_field)
            examples = self.golden_set.get_examples_for_scenario(
                metric_type, match_field, match_value, limit=1
            )
        else:
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
