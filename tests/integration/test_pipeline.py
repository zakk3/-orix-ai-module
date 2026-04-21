# tests/integration/test_pipeline.py
# Интеграционные тесты pipeline с реальными классами проекта
# Запуск: python tests/integration/test_pipeline.py

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
from src.models.enums import MetricType
from src.core.pipeline import AnalysisPipeline


def build_request(series_data: list, metric_type: str = MetricType.LOSS_SHARE.value):
    """Собирает GenerationRequest из списка словарей."""
    items = [OrixSeriesItem(**item) for item in series_data]
    return GenerationRequest(
        metric_type=metric_type,
        period="2025Q3",
        data=OrixMetricInput(series=items, avg=0.8231),
    )


# Серии из реального PDF Golden Set Орикс.
# Каждый эталон — ровно 10 банков, Мой банк заменяет один из аналогов.

CASE_1 = [
    {"serie": "1",  "label": "Банк 1",   "value": 0.004},
    {"serie": "2",  "label": "Банк 2",   "value": 0.097},
    {"serie": "3",  "label": "Банк 3",   "value": 0.114},
    {"serie": "4",  "label": "Банк 4",   "value": 0.196},
    {"serie": "0",  "label": "Мой банк", "value": 0.269},
    {"serie": "6",  "label": "Банк 6",   "value": 0.402},
    {"serie": "7",  "label": "Банк 7",   "value": 0.548},
    {"serie": "8",  "label": "Банк 8",   "value": 0.603},
    {"serie": "9",  "label": "Банк 9",   "value": 1.106},
    {"serie": "10", "label": "Банк 10",  "value": 4.892},
]

# Банк 9 (1.106) заменён на Мой банк — нельзя держать оба с одним значением
CASE_2 = [
    {"serie": "1",  "label": "Банк 1",   "value": 0.004},
    {"serie": "2",  "label": "Банк 2",   "value": 0.097},
    {"serie": "3",  "label": "Банк 3",   "value": 0.114},
    {"serie": "4",  "label": "Банк 4",   "value": 0.196},
    {"serie": "5",  "label": "Банк 5",   "value": 0.269},
    {"serie": "6",  "label": "Банк 6",   "value": 0.402},
    {"serie": "7",  "label": "Банк 7",   "value": 0.548},
    {"serie": "8",  "label": "Банк 8",   "value": 0.603},
    {"serie": "0",  "label": "Мой банк", "value": 1.106},
    {"serie": "10", "label": "Банк 10",  "value": 4.892},
]


def test_case_below_average():
    print("ТЕСТ 1: Мой банк ниже среднего (-67.3%, 5-е место)")
    response = AnalysisPipeline().process_metric(build_request(CASE_1))
    calc = response.calculations

    assert calc.my_bank_value == 0.269
    assert abs(calc.difference_percent - (-67.3)) < 0.1
    assert calc.position == 5
    assert calc.total_banks == 10
    assert calc.deviation_threshold == "существенное"
    assert calc.is_below_average is True
    assert response.validation_passed is True
    print(f"  diff={calc.difference_percent}%  pos={calc.position}/{calc.total_banks}  OK")


def test_case_above_average():
    print("ТЕСТ 2: Мой банк выше среднего (+34.4%, 9-е место)")
    response = AnalysisPipeline().process_metric(build_request(CASE_2))
    calc = response.calculations

    assert abs(calc.difference_percent - 34.4) < 0.2
    assert calc.position == 9
    assert calc.total_banks == 10
    assert calc.is_below_average is False
    print(f"  diff={calc.difference_percent}%  pos={calc.position}/{calc.total_banks}  OK")


def test_unsupported_metric():
    print("ТЕСТ 3: Неподдерживаемая метрика → ValueError")
    request = GenerationRequest(
        metric_type=MetricType.RECOVERY_LEVEL.value,
        data=OrixMetricInput(
            series=[
                OrixSeriesItem(serie="0", label="Мой банк", value=0.5),
                OrixSeriesItem(serie="1", label="Банк 1",   value=0.8),
            ],
            avg=0.65,
        ),
    )
    try:
        AnalysisPipeline().process_metric(request)
        assert False, "Ожидалась ошибка"
    except ValueError as e:
        print(f"  Получена ожидаемая ошибка: {e}  OK")


if __name__ == "__main__":
    test_case_below_average()
    test_case_above_average()
    test_unsupported_metric()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ")