# tests/unit/test_metric3.py
# Запуск: python tests/unit/test_metric3.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.deterministic.metric3_loss_buckets import Metric3Calculator

calc = Metric3Calculator()

# ── Реальные данные из эталонного Excel ───────────────────────────────────────

# Банк 2 → «незначительные отклонения» (total=23.1 пп, ни один бакет >= 10пп)
SERIES_INSIGNIFICANT = [
    {"serie": "1", "label": "<20",   "self": 1.930,  "rest": 0.977},
    {"serie": "2", "label": "20+",   "self": 6.591,  "rest": 7.424},
    {"serie": "3", "label": "100+",  "self": 8.120,  "rest": 10.138},
    {"serie": "4", "label": "350+",  "self": 10.948, "rest": 8.588},
    {"serie": "5", "label": "700+",  "self": 12.668, "rest": 11.547},
    {"serie": "6", "label": "1400+", "self": 18.921, "rest": 14.924},
    {"serie": "7", "label": "3500+", "self": 11.587, "rest": 8.449},
    {"serie": "8", "label": "7000+", "self": 29.234, "rest": 37.954},
]

# Банк 1 → «расхождения» (total=33.3 пп, бакет 7000+ отклоняется на 16.6пп)
SERIES_DIVERGENCE = [
    {"serie": "1", "label": "<20",   "self": 0.875,  "rest": 0.977},
    {"serie": "2", "label": "20+",   "self": 4.831,  "rest": 7.424},
    {"serie": "3", "label": "100+",  "self": 5.551,  "rest": 10.138},
    {"serie": "4", "label": "350+",  "self": 5.128,  "rest": 8.588},
    {"serie": "5", "label": "700+",  "self": 7.661,  "rest": 11.547},
    {"serie": "6", "label": "1400+", "self": 13.131, "rest": 14.924},
    {"serie": "7", "label": "3500+", "self": 8.241,  "rest": 8.449},
    {"serie": "8", "label": "7000+", "self": 54.582, "rest": 37.954},
]

# Банк 5 → «кардинально отличается» (total=147.4пп, max/min бакеты не совпадают)
SERIES_DRASTIC = [
    {"serie": "1", "label": "<20",   "self": 0.141,  "rest": 0.977},
    {"serie": "2", "label": "20+",   "self": 8.325,  "rest": 7.424},
    {"serie": "3", "label": "100+",  "self": 38.708, "rest": 10.138},
    {"serie": "4", "label": "350+",  "self": 52.826, "rest": 8.588},
    {"serie": "5", "label": "700+",  "self": 0.0,    "rest": 11.547},
    {"serie": "6", "label": "1400+", "self": 0.0,    "rest": 14.924},
    {"serie": "7", "label": "3500+", "self": 0.0,    "rest": 8.449},
    {"serie": "8", "label": "7000+", "self": 0.0,    "rest": 37.954},
]

# ── Тесты ─────────────────────────────────────────────────────────────────────

def test_insignificant():
    r = calc.calculate({"series": SERIES_INSIGNIFICANT})
    assert r.extra["scenario_label"] == "незначительные отклонения"
    assert r.extra["total_deviation"] < 25.0
    assert r.extra["any_diff_over_10"] is False
    print(f"✅ незначительные отклонения  total={r.extra['total_deviation']} пп")

def test_divergence():
    r = calc.calculate({"series": SERIES_DIVERGENCE})
    assert r.extra["scenario_label"] == "расхождения"
    assert r.extra["total_deviation"] >= 25.0
    assert r.extra["max_buckets_match"] is True
    assert r.extra["min_buckets_match"] is True
    print(f"✅ расхождения  total={r.extra['total_deviation']} пп  max_diff_bucket='{r.extra['max_diff_bucket']}'")

def test_drastic():
    r = calc.calculate({"series": SERIES_DRASTIC})
    assert r.extra["scenario_label"] == "кардинально отличается"
    assert r.extra["max_buckets_match"] is False
    assert r.extra["has_zero_buckets"] is True
    assert r.extra["concentration_sentence"] != ""
    print(f"✅ кардинально отличается  total={r.extra['total_deviation']} пп  max_bank='{r.extra['max_bank_bucket']}'  max_rest='{r.extra['max_rest_bucket']}'")

if __name__ == "__main__":
    test_insignificant()
    test_divergence()
    test_drastic()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅")
