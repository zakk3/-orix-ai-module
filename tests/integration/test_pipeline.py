# tests/integration/test_pipeline.py
# End-to-end интеграционные тесты pipeline с реальным LLM.
# Запуск: python tests/integration/test_pipeline.py
#
# Требует: файл .env с реальным API-ключом YandexGPT.
# Тест делает реальные запросы к API — занимает ~15-20 секунд.

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
from src.models.enums import MetricType
from src.core.pipeline import AnalysisPipeline


# ── Эталонные серии из data_orix (M1, 10 банков) ─────────────────────────────

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


def build_request(series_data: list, metric_type: str = MetricType.LOSS_SHARE.value) -> GenerationRequest:
    """Собирает GenerationRequest из списка словарей."""
    items = [OrixSeriesItem(**item) for item in series_data]
    return GenerationRequest(
        metric_type=metric_type,
        period="2025Q3",
        data=OrixMetricInput(series=items, avg=0.8231),
    )


# ── Тест: неподдерживаемая метрика (не требует LLM) ──────────────────────────

def test_unsupported_metric():
    print("ТЕСТ: Неподдерживаемая метрика → ValueError")
    request = GenerationRequest(
        metric_type=MetricType.KPUR_VIOLATION.value,
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


# ── End-to-end тесты с реальным LLM ──────────────────────────────────────────

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

    assert abs(calc.difference_percent - expected_diff) < 0.15, \
        f"diff: {calc.difference_percent} != {expected_diff}"
    assert calc.position == expected_pos, \
        f"position: {calc.position} != {expected_pos}"

    assert response.validation_passed, \
        f"Вывод не прошёл валидацию: {response.validation_errors}"
    assert response.quality_score >= 0.70, \
        f"Качество слишком низкое: {response.quality_score}"

    print("  OK")


if __name__ == "__main__":
    # Без LLM
    test_unsupported_metric()

    # С реальным LLM (~15 секунд)
    print("\nЗапускаем end-to-end тесты с реальным LLM...")
    run_case("Эталон 1 — ниже среднего -67.3%, место 5/10", CASE_1, -67.3, 5)
    run_case("Эталон 2 — выше среднего +34.4%, место 9/10", CASE_2, 34.4, 9)
    run_case("Эталон 3 — ниже среднего -51.2%, место 6/10", CASE_3, -51.2, 6)

    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅")
