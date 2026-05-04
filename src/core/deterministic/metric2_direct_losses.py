from typing import Dict, Any, List, Optional, Tuple
import statistics

from src.models.output_models import MetricCalculations


# Минимум кварталов для расчёта тренда
MIN_QUARTERS_FOR_TREND = 3

# Окно для оценки тренда — 3 квартала, как пишут аналитики ОРИКС
TREND_WINDOW = 3

# Порог наклона для классификации тренда (отношение к среднему уровню)
SLOPE_STABLE_THRESHOLD = 0.03      # < 3% — стабильно
SLOPE_SLIGHT_THRESHOLD = 0.12      # < 12% — незначительный тренд

# Пороги для классификации расхождения трендов
RATIO_VOLATILE_THRESHOLD = 5.0     # отношение max/median > 5 — высокая волатильность


class Metric2Calculator:

    METRIC_TYPE = "direct_losses_dynamics"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        # Извлекаем временной ряд: self (мой банк) и rest (среднее)
        self_values, rest_values, labels = self._extract_series(series)

        if len(self_values) < MIN_QUARTERS_FOR_TREND:
            raise ValueError(
                f"Слишком мало кварталов для анализа тренда: "
                f"{len(self_values)} < {MIN_QUARTERS_FOR_TREND}"
            )

        # Соотношения за последние 4 квартала и за последний квартал
        last_q_ratio = self._ratio(self_values[-1], rest_values[-1])
        last_4q_ratio = self._sum_ratio(self_values[-4:], rest_values[-4:])

        # Тренды за последние 4 квартала (даёт более точную картину чем 3)
        bank_trend = self._classify_trend(self_values[-TREND_WINDOW:])
        market_trend = self._classify_trend(rest_values[-TREND_WINDOW:])

        # Расхождение трендов и общая характеристика
        divergence_label = self._divergence_label(
            self_values, rest_values, bank_trend, market_trend
        )

        # Стабильное превышение / занижение на всём периоде
        consistent_above = all(s > r for s, r in zip(self_values, rest_values))
        consistent_below = all(s < r for s, r in zip(self_values, rest_values))

        # Проверяем волатильность (для сценариев типа «драматично отличаются»)
        volatile = self._is_volatile(self_values)

        # Форматируем последний квартал в человеческий вид: "2025Q3" → "Q3 2025"
        last_q_label_human = self._format_quarter(labels[-1])

        # Магнитуда отношения для текста («больше» или «меньше», во сколько раз)
        last_q_direction = "больше" if last_q_ratio > 1 else "меньше"
        last_4q_direction = "больше" if last_4q_ratio > 1 else "меньше"
        last_q_factor = last_q_ratio if last_q_ratio > 1 else 1.0 / last_q_ratio
        last_4q_factor = last_4q_ratio if last_4q_ratio > 1 else 1.0 / last_4q_ratio

        extra: Dict[str, Any] = {
            "last_quarter_label": last_q_label_human,
            "last_quarter_serie": labels[-1],
            "first_quarter_serie": labels[0],
            "total_quarters": len(self_values),

            "bank_trend_3q": bank_trend,
            "market_trend_3q": market_trend,
            "trends_aligned": (bank_trend == market_trend),
            "divergence_label": divergence_label,

            "last_q_ratio": round(last_q_ratio, 2),
            "last_q_factor": round(last_q_factor, 1),
            "last_q_factor_fmt": self._fmt_factor(last_q_factor),
            "last_q_direction": last_q_direction,

            "last_4q_ratio": round(last_4q_ratio, 2),
            "last_4q_factor": round(last_4q_factor, 1),
            "last_4q_factor_fmt": self._fmt_factor(last_4q_factor),
            "last_4q_direction": last_4q_direction,

            "consistent_above_market": consistent_above,
            "consistent_below_market": consistent_below,
            "is_volatile": volatile,

            "self_last": round(self_values[-1], 2),
            "rest_last": round(rest_values[-1], 2),
            "self_avg_period": round(statistics.mean(self_values), 2),
            "rest_avg_period": round(statistics.mean(rest_values), 2),
        }

        # У Metric 2 нет понятий «банк ниже среднего» в рейтинге, но pydantic-модель
        # требует bool. Используем сравнение по последнему кварталу.
        is_below_avg = self_values[-1] < rest_values[-1]

        # Поля position/total_banks/deviation_threshold не применимы к временному ряду —
        # передаём нейтральные значения, чтобы pydantic-модель не падала
        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=round(self_values[-1], 2),
            cluster_avg_value=round(rest_values[-1], 2),
            difference_percent=round(abs((self_values[-1] - rest_values[-1]) / rest_values[-1] * 100), 2)
                if rest_values[-1] != 0 else 0.0,
            is_below_average=is_below_avg,
            position=0,
            total_banks=0,
            deviation_threshold="",
            extra=extra,
        )

    # Извлечение временного ряда

    @staticmethod
    def _extract_series(
        series: List[Dict[str, Any]]
    ) -> Tuple[List[float], List[float], List[str]]:
        # Для Metric 2 у каждого элемента есть self и rest
        self_vals, rest_vals, labels = [], [], []
        for item in series:
            s = item.get("self")
            r = item.get("rest")
            if s is None or r is None:
                raise ValueError(
                    f"Отсутствуют поля self/rest в элементе ряда: {item}"
                )
            if not isinstance(s, (int, float)) or not isinstance(r, (int, float)):
                raise ValueError(f"self и rest должны быть числами: {item}")
            self_vals.append(float(s))
            rest_vals.append(float(r))
            labels.append(str(item.get("serie", item.get("label", ""))))
        return self_vals, rest_vals, labels

    #  Тренды 

    @staticmethod
    def _classify_trend(values: List[float]) -> str:
        # Классификация тренда по относительному наклону регрессии
        if len(values) < 2:
            return "стабильный"

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        if y_mean == 0:
            return "стабильный"

        # Наклон через метод наименьших квадратов
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0

        # Относительный наклон: насколько сильно ряд меняется относительно своего уровня
        relative_slope = slope / y_mean if y_mean != 0 else 0

        if abs(relative_slope) < SLOPE_STABLE_THRESHOLD:
            return "стабильный"
        elif abs(relative_slope) < SLOPE_SLIGHT_THRESHOLD:
            return "незначительный рост" if relative_slope > 0 else "незначительное снижение"
        else:
            return "рост" if relative_slope > 0 else "снижение"

    @staticmethod
    def _divergence_label(
        self_vals: List[float],
        rest_vals: List[float],
        bank_trend: str,
        market_trend: str,
    ) -> str:
        # Классификация по шкале из эталонов: совпадают / незначительно / несколько /
        # существенно / драматично

        # Проверяем сначала драматическое расхождение через волатильность отношений
        ratios = [s / r for s, r in zip(self_vals, rest_vals) if r != 0]
        if ratios:
            max_ratio = max(ratios)
            min_ratio = min(ratios)
            spread = max_ratio / min_ratio if min_ratio > 0 else float('inf')
            # Если разброс отношений колоссальный — это драматичный случай
            if spread > 50:
                return "драматично отличаются"

        # Если тренды совпадают (и не было драматического расхождения) — совпадают
        if bank_trend == market_trend:
            return "в целом совпадают"

        # Один в рост, другой в снижение — самое сильное расхождение направлений
        bank_growing = "рост" in bank_trend
        bank_declining = "снижение" in bank_trend
        market_growing = "рост" in market_trend
        market_declining = "снижение" in market_trend

        opposite_directions = (
            (bank_growing and market_declining)
            or (bank_declining and market_growing)
        )

        if opposite_directions:
            # Если хотя бы один тренд явный (без «незначительн»), то существенно
            both_strong = ("незначительн" not in bank_trend
                          and "незначительн" not in market_trend)
            if both_strong:
                return "существенно отличаются"
            return "несколько отличаются"

        # Один стабилен, другой нет
        if "стабильный" in (bank_trend, market_trend):
            non_stable = bank_trend if bank_trend != "стабильный" else market_trend
            if "незначительн" in non_stable:
                return "незначительно отличаются"
            return "существенно отличаются"

        # Иначе оба — слабые тренды разной направленности
        return "несколько отличаются"

    #  Соотношения и волатильность 

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float:
        # Защищаемся от деления на ноль
        if denominator == 0:
            return float('inf') if numerator > 0 else 1.0
        return numerator / denominator

    @staticmethod
    def _sum_ratio(self_vals: List[float], rest_vals: List[float]) -> float:
        rest_sum = sum(rest_vals)
        if rest_sum == 0:
            return float('inf') if sum(self_vals) > 0 else 1.0
        return sum(self_vals) / rest_sum

    @staticmethod
    def _is_volatile(values: List[float]) -> bool:
        # Волатильность: отношение максимума к медиане
        if len(values) < 4:
            return False
        med = statistics.median(values)
        if med == 0:
            return False
        return max(values) / med > RATIO_VOLATILE_THRESHOLD

    #  Форматирование

    @staticmethod
    def _format_quarter(serie: str) -> str:
        # "2025Q3" → "Q3 2025"
        if "Q" in serie:
            parts = serie.split("Q")
            if len(parts) == 2 and parts[0].isdigit():
                return f"Q{parts[1]} {parts[0]}"
        return serie

    @staticmethod
    def _fmt_factor(val: float) -> str:
        # Форматирование коэффициента: 1.4, 3.6, 241.6 — в стиле эталонов
        if val >= 100:
            return f"{val:.1f}"
        elif val >= 10:
            return f"{val:.1f}"
        else:
            return f"{val:.1f}"