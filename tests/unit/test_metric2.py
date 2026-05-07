# tests/unit/test_metric2.py
# Проверяем расчёты Metric2Calculator (динамика прямых потерь)
# Запуск: py tests/unit/test_metric2.py

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.core.deterministic.metric2_direct_losses import Metric2Calculator


calculator = Metric2Calculator()


def make_series(items):
    """items: список кортежей (serie, label, self_val, rest_val)."""
    return [
        {"serie": s, "label": l, "self": sv, "rest": rv}
        for s, l, sv, rv in items
    ]


# ── Тест 1: тренд — рост по обоим рядам ─────────────────────────────────

def test_trend_growth():
    print("ТЕСТ 1: Тренд — рост (8 кварталов, восходящий тренд)")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 100, 200),
            ("2023Q2", "2023Q2", 110, 210),
            ("2023Q3", "2023Q3", 120, 215),
            ("2023Q4", "2023Q4", 135, 225),
            ("2024Q1", "2024Q1", 145, 230),
            ("2024Q2", "2024Q2", 160, 240),
            ("2024Q3", "2024Q3", 175, 248),
            ("2024Q4", "2024Q4", 195, 260),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2024Q4")

    assert result.metric_type == "direct_losses_dynamics"
    assert result.my_bank_value == 195.0
    assert result.cluster_avg_value == 260.0
    assert result.is_below_average is True  # 195 < 260
    assert result.position is None
    assert result.total_banks is None

    extra = result.extra
    assert extra["my_trend"] == "рост"
    assert extra["avg_trend"] == "рост"
    assert extra["trends_match"] is True
    assert extra["total_quarters"] == 8
    assert extra["volatility_comparison"] in ("выше", "ниже", "сопоставима")

    print(f"  my_trend={extra['my_trend']}, avg_trend={extra['avg_trend']}, "
          f"trends_match={extra['trends_match']}  OK")


# ── Тест 2: тренд — падение банка, стабильный рынок ─────────────────────

def test_trend_decline_opposite():
    print("ТЕСТ 2: Тренд — падение банка, стабильный рынок")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 200, 300),
            ("2023Q2", "2023Q2", 185, 298),
            ("2023Q3", "2023Q3", 170, 302),
            ("2023Q4", "2023Q4", 155, 299),
            ("2024Q1", "2024Q1", 140, 301),
            ("2024Q2", "2024Q2", 125, 300),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2024Q2")

    extra = result.extra
    assert extra["my_trend"] == "падение"
    assert extra["avg_trend"] == "стабильный"
    assert extra["trends_match"] is False

    print(f"  my_trend={extra['my_trend']}, avg_trend={extra['avg_trend']}, "
          f"trends_match={extra['trends_match']}  OK")


# ── Тест 3: QoQ-расчёты ─────────────────────────────────────────────────

def test_qoq_calculations():
    print("ТЕСТ 3: QoQ-расчёты [100, 110, 121]")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 100, 200),
            ("2023Q2", "2023Q2", 110, 210),
            ("2023Q3", "2023Q3", 121, 220),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2023Q3")

    qoq = result.extra["qoq_self"]
    assert len(qoq) == 2
    assert abs(qoq[0] - 10.0) < 0.1, f"QoQ[0]={qoq[0]}, expected 10.0"
    assert abs(qoq[1] - 10.0) < 0.1, f"QoQ[1]={qoq[1]}, expected 10.0"

    print(f"  qoq_self={qoq}  OK")


# ── Тест 4: сравнение волатильности ─────────────────────────────────────

def test_volatility_comparison():
    print("ТЕСТ 4: Сравнение волатильности — банк волатильнее рынка")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 100, 200),
            ("2023Q2", "2023Q2", 180, 205),
            ("2023Q3", "2023Q3", 90,  198),
            ("2023Q4", "2023Q4", 170, 202),
            ("2024Q1", "2024Q1", 80,  200),
            ("2024Q2", "2024Q2", 190, 203),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2024Q2")

    extra = result.extra
    assert extra["volatility_comparison"] == "выше", \
        f"Expected 'выше', got '{extra['volatility_comparison']}'"
    assert extra["my_volatility"] > extra["avg_volatility"]

    print(f"  my_cv={extra['my_volatility']:.4f}, avg_cv={extra['avg_volatility']:.4f}, "
          f"comparison={extra['volatility_comparison']}  OK")


# ── Тест 5: отклонение в последнем квартале ─────────────────────────────

def test_latest_deviation():
    print("ТЕСТ 5: Отклонение — банк ниже рынка на 25%")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 140, 200),
            ("2023Q2", "2023Q2", 145, 200),
            ("2023Q3", "2023Q3", 150, 200),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2023Q3")

    assert result.my_bank_value == 150.0
    assert result.cluster_avg_value == 200.0
    assert abs(result.difference_percent - (-25.0)) < 0.2
    assert result.is_below_average is True
    assert result.deviation_threshold == "среднее"

    print(f"  diff={result.difference_percent}%, "
          f"is_below={result.is_below_average}, "
          f"threshold={result.deviation_threshold}  OK")


# ── Тест 6: всего 2 квартала ────────────────────────────────────────────

def test_two_quarters():
    print("ТЕСТ 6: Edge case — 2 квартала (fallback-логика тренда)")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 100, 200),
            ("2023Q2", "2023Q2", 120, 195),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2023Q2")

    extra = result.extra
    assert result.my_bank_value == 120.0
    assert extra["total_quarters"] == 2
    assert len(extra["qoq_self"]) == 1  # одно QoQ-изменение
    # Тренд через simple_trend: рост 20% > 5% → "рост"
    assert extra["my_trend"] == "рост"

    print(f"  qoq={extra['qoq_self']}, my_trend={extra['my_trend']}  OK")


# ── Тест 7: константные значения ────────────────────────────────────────

def test_constant_values():
    print("ТЕСТ 7: Edge case — константные значения (все кварталы одинаковые)")
    data = {
        "series": make_series([
            ("2023Q1", "2023Q1", 150, 200),
            ("2023Q2", "2023Q2", 150, 200),
            ("2023Q3", "2023Q3", 150, 200),
            ("2023Q4", "2023Q4", 150, 200),
        ])
    }
    result = calculator.calculate(data, "2023Q1-2023Q4")

    extra = result.extra
    assert extra["my_trend"] == "стабильный"
    assert extra["avg_trend"] == "стабильный"
    assert extra["my_volatility"] == 0.0
    assert all(abs(q) < 0.01 for q in extra["qoq_self"])

    print(f"  my_trend={extra['my_trend']}, my_cv={extra['my_volatility']}, "
          f"qoq={extra['qoq_self']}  OK")


# ── Тест 8: интеграция с pipeline ───────────────────────────────────────

def test_pipeline_integration():
    print("ТЕСТ 8: Интеграция с AnalysisPipeline (без LLM)")
    from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
    from src.models.enums import MetricType
    from src.core.pipeline import AnalysisPipeline

    items = [
        {"serie": "2023Q1", "label": "2023Q1", "self": 100, "rest": 200},
        {"serie": "2023Q2", "label": "2023Q2", "self": 110, "rest": 210},
        {"serie": "2023Q3", "label": "2023Q3", "self": 120, "rest": 215},
        {"serie": "2023Q4", "label": "2023Q4", "self": 135, "rest": 225},
    ]
    series = [OrixSeriesItem(**item) for item in items]
    request = GenerationRequest(
        metric_type=MetricType.DIRECT_LOSSES_DYNAMICS.value,
        period="2023Q1-2023Q4",
        data=OrixMetricInput(series=series),
    )

    response = AnalysisPipeline().process_metric(request)
    calc = response.calculations

    assert calc.metric_type == "direct_losses_dynamics"
    assert calc.my_bank_value == 135.0
    assert calc.cluster_avg_value == 225.0
    assert calc.is_below_average is True
    assert calc.position is None
    assert calc.total_banks is None
    assert calc.extra["total_quarters"] == 4
    assert calc.extra["my_trend"] == "рост"

    print(f"  metric={calc.metric_type}, my_val={calc.my_bank_value}, "
          f"trend={calc.extra['my_trend']}, verdict_len={len(response.verdict)}  OK")


if __name__ == "__main__":
    test_trend_growth()
    test_trend_decline_opposite()
    test_qoq_calculations()
    test_volatility_comparison()
    test_latest_deviation()
    test_two_quarters()
    test_constant_values()
    print("\n--- 7 калькулятор-тестов пройдено ---")
    print("Пропускаем test_pipeline_integration (требует .env с API-ключом YandexGPT)")
    # test_pipeline_integration()  # раскомментировать при наличии .env
