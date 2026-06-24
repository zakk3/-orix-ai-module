# tests/unit/test_metric4.py
# Запуск: python tests/unit/test_metric4.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.deterministic.metric4_recovery import Metric4Calculator

calc = Metric4Calculator()

# ── Реальные данные из data_orix.xlsx ─────────────────────────────────────────

# Банк 1 → «соответствует» (diff = −3.8 п.п., |diff| < 5)
SERIES_CORRESPONDS_1 = [
    {"serie": "0", "label": "Мой банк",            "self": 18.026025801169137, "rest": 81.97397419883086},
    {"serie": "1", "label": "Среднее по кластеру", "self": 21.843423955359434, "rest": 78.15657604464056},
]

# Банк 5 → «соответствует» (diff = −2.2 п.п., |diff| < 5)
SERIES_CORRESPONDS_2 = [
    {"serie": "0", "label": "Мой банк",            "self": 19.623112206902317, "rest": 80.37688779309768},
    {"serie": "1", "label": "Среднее по кластеру", "self": 21.843423955359434, "rest": 78.15657604464056},
]

# Банк 3 → «существенные отклонения» (diff = −11.3 п.п., 5 ≤ |diff| < 13)
SERIES_SIGNIFICANT = [
    {"serie": "0", "label": "Мой банк",            "self": 10.566429825981238, "rest": 89.43357017401877},
    {"serie": "1", "label": "Среднее по кластеру", "self": 21.843423955359434, "rest": 78.15657604464056},
]

# Банк 2 → «весьма существенные отклонения» (diff = −14.2 п.п., |diff| ≥ 13)
SERIES_VERY_SIGNIFICANT = [
    {"serie": "0", "label": "Мой банк",            "self": 7.607192167450625,  "rest": 92.39280783254938},
    {"serie": "1", "label": "Среднее по кластеру", "self": 21.843423955359434, "rest": 78.15657604464056},
]

# Банк 4 → «выше среднего» (diff = +15.4 п.п., diff > 5)
SERIES_ABOVE = [
    {"serie": "0", "label": "Мой банк",            "self": 37.27345405854071,  "rest": 62.72654594145929},
    {"serie": "1", "label": "Среднее по кластеру", "self": 21.843423955359434, "rest": 78.15657604464056},
]

# ── Тесты ─────────────────────────────────────────────────────────────────────

def test_corresponds_bank1():
    r = calc.calculate({"series": SERIES_CORRESPONDS_1})
    assert r.extra["scenario_label"] == "соответствует"
    assert r.extra["diff_abs"] == 3.8
    assert r.is_below_average is True
    assert r.extra["is_above_average"] is False
    print(f"✅ соответствует (Банк 1)  diff={r.extra['diff_abs']} п.п.")

def test_corresponds_bank5():
    r = calc.calculate({"series": SERIES_CORRESPONDS_2})
    assert r.extra["scenario_label"] == "соответствует"
    assert r.extra["diff_abs"] == 2.2
    assert r.is_below_average is True
    assert r.extra["is_above_average"] is False
    print(f"✅ соответствует (Банк 5)  diff={r.extra['diff_abs']} п.п.")

def test_significant():
    r = calc.calculate({"series": SERIES_SIGNIFICANT})
    assert r.extra["scenario_label"] == "существенные отклонения"
    assert r.extra["diff_abs"] == 11.3
    assert r.is_below_average is True
    assert r.extra["is_above_average"] is False
    print(f"✅ существенные отклонения  diff={r.extra['diff_abs']} п.п.")

def test_very_significant():
    r = calc.calculate({"series": SERIES_VERY_SIGNIFICANT})
    assert r.extra["scenario_label"] == "весьма существенные отклонения"
    assert r.extra["diff_abs"] == 14.2
    assert r.is_below_average is True
    assert r.extra["is_above_average"] is False
    print(f"✅ весьма существенные отклонения  diff={r.extra['diff_abs']} п.п.")

def test_above_average():
    r = calc.calculate({"series": SERIES_ABOVE})
    assert r.extra["scenario_label"] == "выше среднего"
    assert r.extra["diff_abs"] == 15.4
    assert r.is_below_average is False
    assert r.extra["is_above_average"] is True
    print(f"✅ выше среднего  diff=+{r.extra['diff_abs']} п.п.")

if __name__ == "__main__":
    test_corresponds_bank1()
    test_corresponds_bank5()
    test_significant()
    test_very_significant()
    test_above_average()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅")
