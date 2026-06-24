# tests/unit/test_metric2.py
# Запуск: python tests/unit/test_metric2.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.deterministic.metric2_direct_losses import Metric2Calculator

calc = Metric2Calculator()

# ── Реальные данные из data_orix.xlsx ─────────────────────────────────────────

# Банк 1 → «существенно отличаются»
# bank: рост | market: незначительный рост | last_4q: 1.4× меньше | last_q: 1.1× больше
SERIES_SUBSTANTIAL = [
    {"serie": "2022Q4", "label": "2022Q4", "self": 166.528034,  "rest": 215.834498},
    {"serie": "2023Q1", "label": "2023Q1", "self": 469.738805,  "rest": 178.071402},
    {"serie": "2023Q2", "label": "2023Q2", "self": 491.467764,  "rest": 195.962149},
    {"serie": "2023Q3", "label": "2023Q3", "self": 292.613858,  "rest": 282.820538},
    {"serie": "2023Q4", "label": "2023Q4", "self": 233.641843,  "rest": 250.484822},
    {"serie": "2024Q1", "label": "2024Q1", "self": 325.066955,  "rest": 287.188372},
    {"serie": "2024Q2", "label": "2024Q2", "self": 211.673766,  "rest": 236.349716},
    {"serie": "2024Q3", "label": "2024Q3", "self": 194.471582,  "rest": 247.569997},
    {"serie": "2024Q4", "label": "2024Q4", "self": 179.667188,  "rest": 403.421988},
    {"serie": "2025Q1", "label": "2025Q1", "self": 208.934029,  "rest": 311.279602},
    {"serie": "2025Q2", "label": "2025Q2", "self": 270.307215,  "rest": 403.295799},
    {"serie": "2025Q3", "label": "2025Q3", "self": 353.698862,  "rest": 320.784120},
]

# Банк 3 → «незначительно отличаются»
# bank: незначительный рост | market: незначительный рост | last_4q: 3.5× меньше | last_q: 2.6× меньше
SERIES_INSIGNIFICANT = [
    {"serie": "2022Q4", "label": "2022Q4", "self": 115.499610,  "rest": 215.834498},
    {"serie": "2023Q1", "label": "2023Q1", "self": 34.087501,   "rest": 178.071402},
    {"serie": "2023Q2", "label": "2023Q2", "self": 53.196541,   "rest": 195.962149},
    {"serie": "2023Q3", "label": "2023Q3", "self": 29.955603,   "rest": 282.820538},
    {"serie": "2023Q4", "label": "2023Q4", "self": 27.136946,   "rest": 250.484822},
    {"serie": "2024Q1", "label": "2024Q1", "self": 109.413113,  "rest": 287.188372},
    {"serie": "2024Q2", "label": "2024Q2", "self": 57.402985,   "rest": 236.349716},
    {"serie": "2024Q3", "label": "2024Q3", "self": 31.235502,   "rest": 247.569997},
    {"serie": "2024Q4", "label": "2024Q4", "self": 51.362769,   "rest": 403.421988},
    {"serie": "2025Q1", "label": "2025Q1", "self": 115.486104,  "rest": 311.279602},
    {"serie": "2025Q2", "label": "2025Q2", "self": 125.295917,  "rest": 403.295799},
    {"serie": "2025Q3", "label": "2025Q3", "self": 124.745733,  "rest": 320.784120},
]

# Банк 2 → «несколько отличаются»
# bank: незначительное снижение | market: незначительный рост | last_4q: 3.6× больше | last_q: 3.6× больше
SERIES_MODERATE_BANK2 = [
    {"serie": "2022Q4", "label": "2022Q4", "self": 283.389385,  "rest": 215.834498},
    {"serie": "2023Q1", "label": "2023Q1", "self": 227.875957,  "rest": 178.071402},
    {"serie": "2023Q2", "label": "2023Q2", "self": 336.350695,  "rest": 195.962149},
    {"serie": "2023Q3", "label": "2023Q3", "self": 206.525885,  "rest": 282.820538},
    {"serie": "2023Q4", "label": "2023Q4", "self": 222.162024,  "rest": 250.484822},
    {"serie": "2024Q1", "label": "2024Q1", "self": 748.738443,  "rest": 287.188372},
    {"serie": "2024Q2", "label": "2024Q2", "self": 461.838990,  "rest": 236.349716},
    {"serie": "2024Q3", "label": "2024Q3", "self": 872.083312,  "rest": 247.569997},
    {"serie": "2024Q4", "label": "2024Q4", "self": 1527.451568, "rest": 403.421988},
    {"serie": "2025Q1", "label": "2025Q1", "self": 1192.151675, "rest": 311.279602},
    {"serie": "2025Q2", "label": "2025Q2", "self": 1240.456180, "rest": 403.295799},
    {"serie": "2025Q3", "label": "2025Q3", "self": 1151.046708, "rest": 320.784120},
]

# Банк 4 → «несколько отличаются»
# bank: незначительное снижение | market: незначительный рост | last_4q: 3.4× больше | last_q: 3.2× больше
SERIES_MODERATE_BANK4 = [
    {"serie": "2022Q4", "label": "2022Q4", "self": 1011.120436, "rest": 215.834498},
    {"serie": "2023Q1", "label": "2023Q1", "self": 860.942366,  "rest": 178.071402},
    {"serie": "2023Q2", "label": "2023Q2", "self": 913.337008,  "rest": 195.962149},
    {"serie": "2023Q3", "label": "2023Q3", "self": 985.149948,  "rest": 282.820538},
    {"serie": "2023Q4", "label": "2023Q4", "self": 1592.506508, "rest": 250.484822},
    {"serie": "2024Q1", "label": "2024Q1", "self": 1547.835472, "rest": 287.188372},
    {"serie": "2024Q2", "label": "2024Q2", "self": 1441.165630, "rest": 236.349716},
    {"serie": "2024Q3", "label": "2024Q3", "self": 1186.449532, "rest": 247.569997},
    {"serie": "2024Q4", "label": "2024Q4", "self": 1772.023827, "rest": 403.421988},
    {"serie": "2025Q1", "label": "2025Q1", "self": 1061.599979, "rest": 311.279602},
    {"serie": "2025Q2", "label": "2025Q2", "self": 1007.262646, "rest": 403.295799},
    {"serie": "2025Q3", "label": "2025Q3", "self": 1015.141076, "rest": 320.784120},
]

# Банк 5 → «драматично отличаются»
# bank: незначительное снижение | market: незначительный рост | last_q: 241.6× меньше (spike in Q2 2025)
SERIES_DRAMATIC = [
    {"serie": "2022Q4", "label": "2022Q4", "self": 1.354993,   "rest": 215.834498},
    {"serie": "2023Q1", "label": "2023Q1", "self": 1.927593,   "rest": 178.071402},
    {"serie": "2023Q2", "label": "2023Q2", "self": 0.224926,   "rest": 195.962149},
    {"serie": "2023Q3", "label": "2023Q3", "self": 0.311092,   "rest": 282.820538},
    {"serie": "2023Q4", "label": "2023Q4", "self": 0.337770,   "rest": 250.484822},
    {"serie": "2024Q1", "label": "2024Q1", "self": 14.929056,  "rest": 287.188372},
    {"serie": "2024Q2", "label": "2024Q2", "self": 57.404755,  "rest": 236.349716},
    {"serie": "2024Q3", "label": "2024Q3", "self": 32.388029,  "rest": 247.569997},
    {"serie": "2024Q4", "label": "2024Q4", "self": 2.298213,   "rest": 403.421988},
    {"serie": "2025Q1", "label": "2025Q1", "self": 1.448625,   "rest": 311.279602},
    {"serie": "2025Q2", "label": "2025Q2", "self": 832.640179, "rest": 403.295799},
    {"serie": "2025Q3", "label": "2025Q3", "self": 1.327759,   "rest": 320.784120},
]

# ── Тесты ─────────────────────────────────────────────────────────────────────

def test_substantial():
    r = calc.calculate({"series": SERIES_SUBSTANTIAL})
    e = r.extra
    assert e["divergence_label"] == "существенно отличаются"
    assert e["bank_trend_3q"] == "рост"
    assert e["market_trend_3q"] == "незначительный рост"
    assert e["last_4q_factor"] == 1.4
    assert e["last_4q_direction"] == "меньше"
    assert e["last_q_factor"] == 1.1
    assert e["last_q_direction"] == "больше"
    assert r.is_below_average is False
    print(f"✅ существенно отличаются (Банк 1)  bank={e['bank_trend_3q']}  market={e['market_trend_3q']}")

def test_insignificant():
    r = calc.calculate({"series": SERIES_INSIGNIFICANT})
    e = r.extra
    assert e["divergence_label"] == "незначительно отличаются"
    assert e["bank_trend_3q"] == "незначительный рост"
    assert e["market_trend_3q"] == "незначительный рост"
    assert e["last_4q_factor"] == 3.5
    assert e["last_4q_direction"] == "меньше"
    assert e["consistent_below_market"] is True
    assert r.is_below_average is True
    print(f"✅ незначительно отличаются (Банк 3)  bank={e['bank_trend_3q']}  market={e['market_trend_3q']}")

def test_moderate_bank2():
    r = calc.calculate({"series": SERIES_MODERATE_BANK2})
    e = r.extra
    assert e["divergence_label"] == "несколько отличаются"
    assert e["bank_trend_3q"] == "незначительное снижение"
    assert e["market_trend_3q"] == "незначительный рост"
    assert e["last_4q_factor"] == 3.6
    assert e["last_4q_direction"] == "больше"
    assert r.is_below_average is False
    print(f"✅ несколько отличаются (Банк 2)  bank={e['bank_trend_3q']}  market={e['market_trend_3q']}")

def test_moderate_bank4():
    r = calc.calculate({"series": SERIES_MODERATE_BANK4})
    e = r.extra
    assert e["divergence_label"] == "несколько отличаются"
    assert e["bank_trend_3q"] == "незначительное снижение"
    assert e["market_trend_3q"] == "незначительный рост"
    assert e["last_4q_factor"] == 3.4
    assert e["last_4q_direction"] == "больше"
    assert e["consistent_above_market"] is True
    assert r.is_below_average is False
    print(f"✅ несколько отличаются (Банк 4)  bank={e['bank_trend_3q']}  market={e['market_trend_3q']}")

def test_dramatic():
    r = calc.calculate({"series": SERIES_DRAMATIC})
    e = r.extra
    assert e["divergence_label"] == "драматично отличаются"
    assert e["bank_trend_3q"] == "незначительное снижение"
    assert e["market_trend_3q"] == "незначительный рост"
    assert e["last_q_factor"] == 241.6
    assert e["last_q_direction"] == "меньше"
    assert e["loss_level"] == "невысоким"
    assert r.is_below_average is True
    print(f"✅ драматично отличаются (Банк 5)  last_q={e['last_q_factor']}× {e['last_q_direction']}  volatility={e['volatility_level']}")

if __name__ == "__main__":
    test_substantial()
    test_insignificant()
    test_moderate_bank2()
    test_moderate_bank4()
    test_dramatic()
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅")
