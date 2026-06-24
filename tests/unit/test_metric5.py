# tests/unit/test_metric5.py
# Запуск: python tests/unit/test_metric5.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.deterministic.metric5_concentration import Metric5Calculator

calc = Metric5Calculator()

# ── Реальные данные из data_orix.xlsx ─────────────────────────────────────────

# Банк 1 → «некоторые различия»
# n_sig=2, top2_match=False, max_diff=21.4 (Внешние причины), alert=True (Недостатки -13.7 п.п.)
SERIES_SOME_DIFFERENCES_B1 = [
    {"serie": "1", "label": "Недостатки процессов", "self": 2.2941903205519574,  "rest": 15.980407778883205},
    {"serie": "2", "label": "Действия персонала",   "self": 5.345588718463157,   "rest": 15.314944330607721},
    {"serie": "3", "label": "Сбои систем",          "self": 12.76814397436921,   "rest": 10.51556149203101},
    {"serie": "4", "label": "Внешние причины",      "self": 79.59207698661568,   "rest": 58.18908639847807},
]

# Банк 5 → «некоторые различия»
# n_sig=2, top2_match=False, max_diff=17.1 (Сбои систем), alert=True (Недостатки -14.2 п.п.)
SERIES_SOME_DIFFERENCES_B5 = [
    {"serie": "1", "label": "Недостатки процессов", "self": 1.786167753275869,   "rest": 15.980407778883205},
    {"serie": "2", "label": "Действия персонала",   "self": 17.634102093950702,  "rest": 15.314944330607721},
    {"serie": "3", "label": "Сбои систем",          "self": 27.61224676301938,   "rest": 10.51556149203101},
    {"serie": "4", "label": "Внешние причины",      "self": 52.96748338975405,   "rest": 58.18908639847807},
]

# Банк 3 → «некоторые отличия»
# n_sig=1 (только Недостатки процессов -12 п.п.), alert=True
SERIES_SLIGHT = [
    {"serie": "1", "label": "Недостатки процессов", "self": 3.9329138658764453,  "rest": 15.980407778883205},
    {"serie": "2", "label": "Действия персонала",   "self": 19.647926161813803,  "rest": 15.314944330607721},
    {"serie": "3", "label": "Сбои систем",          "self": 9.114450164835818,   "rest": 10.51556149203101},
    {"serie": "4", "label": "Внешние причины",      "self": 67.30470980747393,   "rest": 58.18908639847807},
]

# Банк 4 → «умеренные различия»
# n_sig=2, top2_match=True (обе стороны: Внешние причины + Недостатки процессов), alert=False
SERIES_MODERATE = [
    {"serie": "1", "label": "Недостатки процессов", "self": 26.644582677271178,  "rest": 15.980407778883205},
    {"serie": "2", "label": "Действия персонала",   "self": 20.330145848,        "rest": 15.314944330607721},
    {"serie": "3", "label": "Сбои систем",          "self": 10.51556149203101,   "rest": 10.51556149203101},
    {"serie": "4", "label": "Внешние причины",      "self": 42.509709982697812,  "rest": 58.18908639847807},
]

# Банк 2 → «значительно отличается»
# n_sig=2, max_diff=30.9 (Внешние причины ≥ 25 п.п.), top2_match=False, alert=True
SERIES_SIGNIFICANT = [
    {"serie": "1", "label": "Недостатки процессов", "self": 1.8009318912293226,  "rest": 15.980407778883205},
    {"serie": "2", "label": "Действия персонала",   "self": 5.348738789594544,   "rest": 15.314944330607721},
    {"serie": "3", "label": "Сбои систем",          "self": 3.7919588305034586,  "rest": 10.51556149203101},
    {"serie": "4", "label": "Внешние причины",      "self": 89.05837048867268,   "rest": 58.18908639847807},
]

# ── Тесты ─────────────────────────────────────────────────────────────────────

def test_some_differences_bank1():
    r = calc.calculate({"series": SERIES_SOME_DIFFERENCES_B1})
    e = r.extra
    assert e["scenario_label"] == "некоторые различия"
    assert e["n_significant"] == 2
    assert e["top2_match"] is False
    assert e["top2_bank"] == ["Внешние причины", "Сбои систем"]
    assert e["top2_cluster"] == ["Внешние причины", "Недостатки процессов"]
    assert e["max_diff_source"] == "Внешние причины"
    assert e["max_diff_abs"] == 21.4
    assert e["has_nedostatki_alert"] is True
    assert e["nedostatki_diff_abs"] == 13.7
    print(f"✅ некоторые различия (Банк 1)  n_sig={e['n_significant']}  max_diff={e['max_diff_abs']} п.п.  alert=True")

def test_some_differences_bank5():
    r = calc.calculate({"series": SERIES_SOME_DIFFERENCES_B5})
    e = r.extra
    assert e["scenario_label"] == "некоторые различия"
    assert e["n_significant"] == 2
    assert e["top2_match"] is False
    assert e["top2_bank"] == ["Внешние причины", "Сбои систем"]
    assert e["max_diff_source"] == "Сбои систем"
    assert e["max_diff_abs"] == 17.1
    assert e["has_nedostatki_alert"] is True
    assert e["nedostatki_diff_abs"] == 14.2
    print(f"✅ некоторые различия (Банк 5)  n_sig={e['n_significant']}  max_diff={e['max_diff_abs']} п.п.  alert=True")

def test_slight():
    r = calc.calculate({"series": SERIES_SLIGHT})
    e = r.extra
    assert e["scenario_label"] == "некоторые отличия"
    assert e["n_significant"] == 1
    assert e["max_diff_source"] == "Недостатки процессов"
    assert e["max_diff_abs"] == 12.0
    assert e["has_nedostatki_alert"] is True
    print(f"✅ некоторые отличия (Банк 3)  n_sig={e['n_significant']}  max_diff={e['max_diff_abs']} п.п.  alert=True")

def test_moderate():
    r = calc.calculate({"series": SERIES_MODERATE})
    e = r.extra
    assert e["scenario_label"] == "умеренные различия"
    assert e["n_significant"] == 2
    assert e["top2_match"] is True
    assert e["top2_bank"] == ["Внешние причины", "Недостатки процессов"]
    assert e["top2_cluster"] == ["Внешние причины", "Недостатки процессов"]
    assert e["has_nedostatki_alert"] is False
    print(f"✅ умеренные различия (Банк 4)  n_sig={e['n_significant']}  top2_match=True  alert=False")

def test_significant():
    r = calc.calculate({"series": SERIES_SIGNIFICANT})
    e = r.extra
    assert e["scenario_label"] == "значительно отличается"
    assert e["n_significant"] == 2
    assert e["top2_match"] is False
    assert e["max_diff_source"] == "Внешние причины"
    assert e["max_diff_abs"] == 30.9
    assert e["has_nedostatki_alert"] is True
    assert e["nedostatki_diff_abs"] == 14.2
    print(f"✅ значительно отличается (Банк 2)  n_sig={e['n_significant']}  max_diff={e['max_diff_abs']} п.п.  alert=True")

if __name__ == "__main__":
    test_some_differences_bank1()
    test_some_differences_bank5()
    test_slight()
    test_moderate()
    test_significant()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅")
