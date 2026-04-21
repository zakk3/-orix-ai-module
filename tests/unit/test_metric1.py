# tests/unit/test_metric1_vs_golden_set.py
# Проверяем расчёты против реальных эталонов из PDF Golden Set Орикс
# Запуск: python tests/unit/test_metric1_vs_golden_set.py

MY_BANK_KEYWORDS = ("мой банк", "my bank")
AVERAGE_KEYWORDS = ("среднее", "average", "mean")


def find_my_bank(series):
    for item in series:
        if any(kw in str(item.get("label", "")).lower() for kw in MY_BANK_KEYWORDS):
            return item
    return None


def calc_diff_pct(value, avg):
    return ((value - avg) / avg) * 100.0


def calc_position(series, my_value):
    values = [
        float(item["value"])
        for item in series
        if not any(kw in str(item.get("label", "")).lower() for kw in AVERAGE_KEYWORDS)
        and isinstance(item.get("value"), (int, float))
    ]
    sorted_vals = sorted(values)
    total = len(sorted_vals)
    for i, val in enumerate(sorted_vals, 1):
        if abs(val - my_value) < 1e-6:
            return i, total
    return None, total


def classify(abs_diff):
    if abs_diff < 10: return "незначительное"
    if abs_diff < 30: return "среднее"
    return "существенное"


def run_case(label, series, avg, expected_diff, expected_pos, expected_total, expected_threshold):
    print(f"\nТЕСТ: {label}")
    my = find_my_bank(series)
    diff = calc_diff_pct(my["value"], avg)
    pos, total = calc_position(series, my["value"])
    threshold = classify(abs(diff))

    assert abs(diff - expected_diff) < 0.15, f"diff: {diff:.1f} != {expected_diff}"
    assert pos == expected_pos and total == expected_total, f"position: {pos}/{total} != {expected_pos}/{expected_total}"
    assert threshold == expected_threshold, f"threshold: {threshold} != {expected_threshold}"
    print(f"  diff={diff:.1f}%  pos={pos}/{total}  class={threshold}  OK")


# Каждый эталон — свой набор банков (из реального PDF Golden Set Орикс).
# Важно: в каждом случае Мой банк заменяет одного из банков в рейтинге,
# поэтому серии не совпадают и нельзя использовать общий BASE.

# Эталон 1: Мой банк = 0.269, занимает 5-е место из 10
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

# Эталон 2: Мой банк = 1.106, занимает 9-е место из 10
# Банк 9 (1.106) заменён на Мой банк — иначе будет два элемента с одним значением
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

# Эталон 3: Мой банк = 0.402, занимает 6-е место из 10
# Банк 6 (0.402) заменён на Мой банк
CASE_3 = [
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

if __name__ == "__main__":
    run_case("Эталон 1 — -67.3%, 5-е место",  CASE_1, avg=0.8231,
             expected_diff=-67.3, expected_pos=5,  expected_total=10, expected_threshold="существенное")

    run_case("Эталон 2 — +34.4%, 9-е место",  CASE_2, avg=0.8231,
             expected_diff=34.4,  expected_pos=9,  expected_total=10, expected_threshold="существенное")

    run_case("Эталон 3 — -51.2%, 6-е место",  CASE_3, avg=0.8231,
             expected_diff=-51.2, expected_pos=6,  expected_total=10, expected_threshold="существенное")

    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ")