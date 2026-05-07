# src/core/deterministic/metric2_direct_losses.py
# Метрика 2: Динамика прямых потерь (DIRECT_LOSSES_DYNAMICS)
# Анализ временных рядов: тренды, QoQ, волатильность, темпы роста.

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from src.models.output_models import MetricCalculations
from src.models.enums import DeviationThreshold


THRESHOLD_INSIGNIFICANT = 10.0
THRESHOLD_MODERATE = 30.0

TREND_GROWTH = "рост"
TREND_DECLINE = "падение"
TREND_STABLE = "стабильный"

# Нормализованный наклон > 2% среднего на квартал → рост
TREND_SLOPE_THRESHOLD = 0.02


class Metric2Calculator:
    """Расчёт динамики прямых потерь по кварталам."""

    METRIC_TYPE = "direct_losses_dynamics"

    def calculate(self, data: Dict[str, Any], period: str) -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("Поле 'series' пусто или отсутствует")

        self_values, rest_values, quarter_labels = self._extract_timeseries(series)
        n = len(self_values)

        if n < 2:
            raise ValueError("Для анализа динамики необходимо минимум 2 квартала")

        # Последний квартал
        my_val = self_values[-1]
        avg_val = rest_values[-1]

        # Отклонение в последнем квартале
        if avg_val != 0:
            diff_pct = round((my_val - avg_val) / avg_val * 100.0, 2)
        else:
            diff_pct = 0.0

        is_below = my_val < avg_val
        diff_abs = abs(diff_pct)

        # Классификация отклонения
        deviation_threshold = self._classify(diff_abs).value

        # Тренды
        my_trend = self._classify_trend(self_values)
        avg_trend = self._classify_trend(rest_values)
        trends_match = (my_trend == avg_trend)

        # QoQ
        qoq_self = self._calculate_qoq(self_values)
        qoq_rest = self._calculate_qoq(rest_values)
        latest_qoq_self = qoq_self[-1] if qoq_self else None
        latest_qoq_rest = qoq_rest[-1] if qoq_rest else None

        # CAGR
        my_growth_rate = self._calculate_cagr(self_values)
        avg_growth_rate = self._calculate_cagr(rest_values)

        # Волатильность
        my_cv = self._calculate_cv(self_values)
        avg_cv = self._calculate_cv(rest_values)
        volatility_comparison = self._compare_volatility(my_cv, avg_cv)

        # Лейблы
        deviation_direction = "ниже" if is_below else "выше"
        magnitude_label = self._magnitude_label(diff_pct, is_below)
        deviation_level = self._deviation_level(diff_abs)

        # Форматированные строки
        qoq_self_fmt = [self._fmt_pct(v) for v in qoq_self]
        qoq_rest_fmt = [self._fmt_pct(v) for v in qoq_rest]

        extra = {
            "my_trend": my_trend,
            "avg_trend": avg_trend,
            "trends_match": trends_match,
            "my_growth_rate": round(my_growth_rate, 4) if my_growth_rate is not None else None,
            "avg_growth_rate": round(avg_growth_rate, 4) if avg_growth_rate is not None else None,
            "my_growth_rate_fmt": self._fmt_pct(my_growth_rate) if my_growth_rate is not None else "—",
            "avg_growth_rate_fmt": self._fmt_pct(avg_growth_rate) if avg_growth_rate is not None else "—",
            "qoq_self": [round(v, 2) for v in qoq_self],
            "qoq_rest": [round(v, 2) for v in qoq_rest],
            "qoq_self_fmt": qoq_self_fmt,
            "qoq_rest_fmt": qoq_rest_fmt,
            "latest_qoq_self": round(latest_qoq_self, 2) if latest_qoq_self is not None else None,
            "latest_qoq_rest": round(latest_qoq_rest, 2) if latest_qoq_rest is not None else None,
            "latest_qoq_self_fmt": self._fmt_pct(latest_qoq_self) if latest_qoq_self is not None else "—",
            "latest_qoq_rest_fmt": self._fmt_pct(latest_qoq_rest) if latest_qoq_rest is not None else "—",
            "my_volatility": round(my_cv, 4) if my_cv is not None else None,
            "avg_volatility": round(avg_cv, 4) if avg_cv is not None else None,
            "my_volatility_fmt": self._fmt_val(my_cv) if my_cv is not None else "—",
            "avg_volatility_fmt": self._fmt_val(avg_cv) if avg_cv is not None else "—",
            "volatility_comparison": volatility_comparison,
            "total_quarters": n,
            "quarter_labels": quarter_labels,
            "self_values": [round(v, 4) for v in self_values],
            "rest_values": [round(v, 4) for v in rest_values],
            "self_values_fmt": [self._fmt_val(v) for v in self_values],
            "rest_values_fmt": [self._fmt_val(v) for v in rest_values],
            "magnitude_label": magnitude_label,
            "deviation_direction": deviation_direction,
            "deviation_level": deviation_level,
            "direction": deviation_direction,
        }

        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=round(my_val, 4),
            cluster_avg_value=round(avg_val, 4),
            difference_percent=diff_pct,
            is_below_average=is_below,
            position=None,
            total_banks=None,
            deviation_threshold=deviation_threshold,
            extra=extra,
        )

    # ── Извлечение временного ряда ────────────────────────────────────────

    def _extract_timeseries(
        self, series: List[Dict]
    ) -> Tuple[List[float], List[float], List[str]]:
        """Извлекает self/rest массивы с сортировкой по кварталам."""
        self_vals = []
        rest_vals = []
        labels = []

        for item in series:
            s = item.get("self") or item.get("self_")
            r = item.get("rest")
            if s is None:
                raise ValueError(
                    f"Поле 'self' отсутствует в элементе ряда: {item.get('serie', item)}"
                )
            if r is None:
                raise ValueError(
                    f"Поле 'rest' отсутствует в элементе ряда: {item.get('serie', item)}"
                )
            try:
                self_vals.append(float(s))
                rest_vals.append(float(r))
                labels.append(str(item.get("serie", item.get("label", ""))))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Некорректное числовое значение в элементе {item.get('serie', item)}: {e}"
                )

        return self_vals, rest_vals, labels

    # ── Тренд-классификация (линейная регрессия) ─────────────────────────

    def _classify_trend(self, values: List[float]) -> str:
        """Классификация тренда через нормализованный наклон OLS."""
        n = len(values)
        mean_val = sum(values) / n

        if n < 4:
            return self._simple_trend(values)

        if mean_val == 0:
            return TREND_STABLE

        # OLS slope = sum((xi - x̄)(yi - ȳ)) / sum((xi - x̄)^2)
        x_mean = (n - 1) / 2.0
        numerator = 0.0
        denominator = 0.0
        for i, y in enumerate(values):
            dx = i - x_mean
            dy = y - mean_val
            numerator += dx * dy
            denominator += dx * dx

        if denominator == 0:
            return TREND_STABLE

        slope = numerator / denominator
        normalized_slope = slope / mean_val

        if normalized_slope > TREND_SLOPE_THRESHOLD:
            return TREND_GROWTH
        elif normalized_slope < -TREND_SLOPE_THRESHOLD:
            return TREND_DECLINE
        else:
            return TREND_STABLE

    def _simple_trend(self, values: List[float]) -> str:
        """Fallback: сравнение первой и последней точки при <4 кварталах."""
        n = len(values)
        if n < 2:
            return TREND_STABLE
        first, last = values[0], values[-1]
        if first == 0:
            return TREND_STABLE
        change = (last - first) / abs(first)
        if change > 0.05:
            return TREND_GROWTH
        elif change < -0.05:
            return TREND_DECLINE
        return TREND_STABLE

    # ── QoQ-изменения ────────────────────────────────────────────────────

    def _calculate_qoq(self, values: List[float]) -> List[float]:
        """Поквартальные процентные изменения."""
        result = []
        for i in range(1, len(values)):
            prev, cur = values[i - 1], values[i]
            if prev != 0:
                result.append(round((cur - prev) / abs(prev) * 100.0, 2))
            else:
                result.append(0.0)
        return result

    # ── CAGR ─────────────────────────────────────────────────────────────

    def _calculate_cagr(self, values: List[float]) -> float | None:
        """Compound Annual Growth Rate (среднеквартальный)."""
        n = len(values)
        if n < 2:
            return None
        first, last = values[0], values[-1]
        if first <= 0:
            # Fallback: среднее QoQ
            qoq = self._calculate_qoq(values)
            if not qoq:
                return None
            return sum(qoq) / len(qoq) / 100.0
        return (last / first) ** (1.0 / (n - 1)) - 1.0

    # ── Коэффициент вариации ─────────────────────────────────────────────

    def _calculate_cv(self, values: List[float]) -> float | None:
        """Coefficient of Variation = std / mean."""
        n = len(values)
        if n < 2:
            return None
        mean_val = sum(values) / n
        if mean_val == 0:
            return None
        variance = sum((x - mean_val) ** 2 for x in values) / n
        std_dev = math.sqrt(variance)
        return std_dev / mean_val

    def _compare_volatility(self, my_cv: float | None, avg_cv: float | None) -> str:
        """Сравнение волатильности банка и рынка."""
        if my_cv is None or avg_cv is None:
            return "недостаточно данных"
        if avg_cv == 0:
            return "выше" if my_cv > 0 else "сопоставима"
        ratio = my_cv / avg_cv
        if ratio > 1.1:
            return "выше"
        elif ratio < 0.9:
            return "ниже"
        return "сопоставима"

    # ── Классификация отклонения ─────────────────────────────────────────

    def _classify(self, diff_abs: float) -> DeviationThreshold:
        if diff_abs < THRESHOLD_INSIGNIFICANT:
            return DeviationThreshold.INSIGNIFICANT
        elif diff_abs < THRESHOLD_MODERATE:
            return DeviationThreshold.MODERATE
        else:
            return DeviationThreshold.SIGNIFICANT

    def _magnitude_label(self, diff_pct: float, is_below: bool) -> str:
        """Нейтральная числовая метка: «на 114% выше среднего»."""
        direction = "ниже" if is_below else "выше"
        adiff = abs(diff_pct)
        if adiff < 0.5:
            return "на уровне среднего"
        return f"на {adiff:.0f}% {direction} среднего"

    def _deviation_level(self, diff_abs: float) -> str:
        """Уровень отклонения по отраслевым порогам."""
        if diff_abs < 10:
            return "соответствует норме"
        elif diff_abs < 30:
            return "приближается к пороговому уровню"
        elif diff_abs < 96:
            return "превышает пороговый уровень"
        else:
            return "критически превышает допустимый порог"

    # ── Форматирование ───────────────────────────────────────────────────

    @staticmethod
    def _fmt_pct(val: float | None) -> str:
        """Проценты: 14.5 → '14,50 %'"""
        if val is None:
            return "—"
        return f"{val:.2f}".replace(".", ",") + " %"

    @staticmethod
    def _fmt_val(val: float | None) -> str:
        """Число: 0.423 → '0,42'"""
        if val is None:
            return "—"
        return f"{val:.2f}".replace(".", ",")
