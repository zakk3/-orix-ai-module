

'''
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
        metric_type=MetricType.NET_LOSSES_DYNAMICS.value,
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


# ── Метрика 2: Динамика прямых потерь ──────────────────────────────────

METRIC2_CASE_GROWING = [
    {"serie": "2023Q1", "label": "2023Q1", "self": 100, "rest": 200},
    {"serie": "2023Q2", "label": "2023Q2", "self": 110, "rest": 210},
    {"serie": "2023Q3", "label": "2023Q3", "self": 120, "rest": 215},
    {"serie": "2023Q4", "label": "2023Q4", "self": 135, "rest": 225},
]

METRIC2_CASE_DECLINING = [
    {"serie": "2023Q1", "label": "2023Q1", "self": 200, "rest": 300},
    {"serie": "2023Q2", "label": "2023Q2", "self": 185, "rest": 298},
    {"serie": "2023Q3", "label": "2023Q3", "self": 170, "rest": 302},
    {"serie": "2023Q4", "label": "2023Q4", "self": 155, "rest": 299},
    {"serie": "2024Q1", "label": "2024Q1", "self": 140, "rest": 301},
    {"serie": "2024Q2", "label": "2024Q2", "self": 125, "rest": 300},
]


def build_metric2_request(series_data: list):
    items = [OrixSeriesItem(**item) for item in series_data]
    return GenerationRequest(
        metric_type=MetricType.DIRECT_LOSSES_DYNAMICS.value,
        period="2023Q1-2024Q2",
        data=OrixMetricInput(series=items),
    )


def test_metric2_growth():
    print("ТЕСТ M2.1: Метрика 2 — растущий тренд банка")
    response = AnalysisPipeline().process_metric(build_metric2_request(METRIC2_CASE_GROWING))
    calc = response.calculations

    assert calc.metric_type == "direct_losses_dynamics"
    assert calc.my_bank_value == 135.0
    assert calc.cluster_avg_value == 225.0
    assert calc.is_below_average is True
    assert calc.position is None
    assert calc.total_banks is None
    assert calc.deviation_threshold is not None
    assert calc.extra["my_trend"] == "рост"
    assert calc.extra["total_quarters"] == 4
    assert calc.extra["trends_match"] is True

    print(f"  metric={calc.metric_type}, diff={calc.difference_percent}%, "
          f"my_trend={calc.extra['my_trend']}, "
          f"avg_trend={calc.extra['avg_trend']}, "
          f"verdict_len={len(response.verdict)}  OK")


def test_metric2_decline():
    print("ТЕСТ M2.2: Метрика 2 — падающий тренд банка")
    response = AnalysisPipeline().process_metric(build_metric2_request(METRIC2_CASE_DECLINING))
    calc = response.calculations

    assert calc.my_bank_value == 125.0
    assert calc.cluster_avg_value == 300.0
    assert calc.is_below_average is True
    assert calc.extra["my_trend"] == "падение"
    assert calc.extra["avg_trend"] == "стабильный"
    assert calc.extra["trends_match"] is False
    assert calc.extra["total_quarters"] == 6
    assert calc.extra["volatility_comparison"] in ("выше", "ниже", "сопоставима")

    print(f"  diff={calc.difference_percent}%, "
          f"my_trend={calc.extra['my_trend']}, "
          f"avg_trend={calc.extra['avg_trend']}, "
          f"trends_match={calc.extra['trends_match']}, "
          f"verdict_len={len(response.verdict)}  OK")


if __name__ == "__main__":
    test_case_below_average()
    test_case_above_average()
    test_unsupported_metric()
    test_metric2_growth()
    test_metric2_decline()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ")

'''
# tests/integration/test_llm_pipeline.py
# End-to-end тест: полный pipeline с реальным LLM на 3 эталонах PDF Орикс.
# Запуск: python tests/integration/test_llm_pipeline.py
#
# Требует: файл .env с реальным API-ключом YandexGPT.
# Тест делает реальные запросы к API — занимает ~10-15 секунд.

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
from src.models.enums import MetricType
from src.core.pipeline import AnalysisPipeline


# Эталонные серии из PDF Golden Set Орикс
CASE_1 = [  # Мой банк = 0.269, ожидается -67.3%, 5-е место
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

CASE_2 = [  # Мой банк = 1.106, ожидается +34.4%, 9-е место
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

CASE_3 = [  # Мой банк = 0.402, ожидается -51.2%, 6-е место
    {"serie": "1",  "label": "Банк 1",   "value": 0.004},
    {"serie": "2",  "label": "Банк 2",   "value": 0.097},
    {"serie": "3",  "label": "Банк 3",   "value": 0.114},
    {"serie": "4",  "label": "Банк 4",   "value": 0.196},
    {"serie": "5",  "label": "Банк 5",   "value": 0.269},
    {"serie": "0",  "label": "Мой банк", "value": 0.402},
    {"serie": "7",  "label": "Банк 7",   "value": 0.548},
    {"serie": "8",  "label": "Банк 8",   "value": 0.603},
    {"serie": "9",  "label": "Банк 9",   "value": 1.106},
    {"serie": "10", "label": "Банк 10",  "value": 4.892},
]


def build_request(series_data: list) -> GenerationRequest:
    items = [OrixSeriesItem(**item) for item in series_data]
    return GenerationRequest(
        metric_type=MetricType.LOSS_SHARE.value,
        period="2025Q3",
        data=OrixMetricInput(series=items, avg=0.8231),
    )


def run_case(name: str, series_data: list, expected_diff: float, expected_pos: int):
    print(f"\nТЕСТ: {name}")

    pipeline = AnalysisPipeline()
    response = pipeline.process_metric(build_request(series_data))

    calc = response.calculations
    print(f"  Расчёты: diff={calc.difference_percent}%  pos={calc.position}/{calc.total_banks}")
    print(f"  Качество: {response.quality_score} | Валидация: {response.validation_passed}")
    print(f"  Ошибки: {response.validation_errors or 'нет'}")
    print(f"  Вывод ({len(response.verdict)} симв.):")
    print(f"  {response.verdict[:120]}...")

    # Проверяем расчёты
    assert abs(calc.difference_percent - expected_diff) < 0.15, \
        f"diff: {calc.difference_percent} != {expected_diff}"
    assert calc.position == expected_pos, \
        f"position: {calc.position} != {expected_pos}"

    # Проверяем качество вывода от LLM
    assert response.validation_passed, \
        f"Вывод не прошёл валидацию: {response.validation_errors}"
    assert response.quality_score >= 0.70, \
        f"Качество слишком низкое: {response.quality_score}"

    print("  OK")


if __name__ == "__main__":
    print("Запускаем end-to-end тесты с реальным LLM (~15 секунд)...")

    run_case("Эталон 1 — ниже среднего -67.3%, место 5/10", CASE_1, -67.3, 5)
    run_case("Эталон 2 — выше среднего +34.4%, место 9/10", CASE_2, 34.4, 9)
    run_case("Эталон 3 — ниже среднего -51.2%, место 6/10", CASE_3, -51.2, 6)

    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ — LLM + pipeline работают корректно")