from typing import Dict, Any, List, Optional, Tuple
import statistics

from src.models.output_models import MetricCalculations
from src.models.enums import DeviationThreshold


# Ключевые слова для определения строки «Мой банк» и строки «Среднее» в series
MY_BANK_KEYWORDS = ("мой банк", "my bank", "мой_банк")
AVERAGE_KEYWORDS = ("среднее", "average", "mean")

# Пороги для классификации отклонения в процентах
THRESHOLD_INSIGNIFICANT = 10.0
THRESHOLD_MODERATE = 30.0

# Коэффициент для определения аномалий по методу IQR
IQR_MULT = 1.5


class Metric1Calculator:

    METRIC_TYPE = "loss_share"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        # Находим строку «Мой банк» и извлекаем значение
        my_bank = self._find_my_bank(series)
        if my_bank is None:
            raise ValueError("Мой банк не найден в данных")

        my_val = my_bank.get("value")
        if my_val is None:
            raise ValueError("У элемента 'Мой банк' отсутствует поле value")

        # Список остальных банков без «Мой банк» и «Среднее»
        other_banks = self._other_banks(series)
        other_values = [b["value"] for b in other_banks]

        # Среднее берём из входных данных, если не передано — считаем сами
        avg_val = data.get("avg") or self._calculate_average(series)
        if avg_val == 0:
            raise ValueError("Среднее равно нулю — деление невозможно")

        # Абсолютное отклонение от среднего в процентах
        diff_abs = abs((my_val - avg_val) / avg_val * 100.0)
        position, total = self._calculate_position(series, my_val)

        # Медиана по всей выборке включая «Мой банк»
        median_value = statistics.median(other_values + [my_val])

        # Аномалии только среди других банков; скорректированное среднее без них
        outliers = self._detect_outliers(other_banks)
        adjusted_avg = self._adjusted_average(other_values, outliers)

        # Собираем дополнительные поля — LLM использует их при генерации текста
        extra: Dict[str, Any] = {
            "representativeness_pct": data.get("representativeness", 62),
            "deviation_direction": "ниже" if my_val < avg_val else "выше",
            "deviation_level": self._deviation_level(my_val),
            "magnitude_label": self._magnitude_label(diff_abs, my_val, avg_val),
            "median_value": round(median_value, 4),
            "median_value_fmt": self._fmt_ru(median_value, 4),
            "my_bank_vs_median": "ниже" if my_val < median_value else "выше",
            "has_outliers": bool(outliers),
        }

        # Если есть аномалии — добавляем информацию о самой крупной
        if outliers:
            top = max(outliers, key=lambda b: b["value"])
            extra.update({
                "outlier_label": top["label"],
                "outlier_value": round(float(top["value"]), 4),
                "outlier_value_fmt": self._fmt_ru(top["value"], 4),
                "outliers_count": len(outliers),
            })
            if adjusted_avg is not None:
                extra["adjusted_avg"] = round(adjusted_avg, 4)
                extra["adjusted_avg_fmt"] = self._fmt_ru(adjusted_avg, 4)

        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=round(float(my_val), 4),
            cluster_avg_value=round(float(avg_val), 4),
            difference_percent=round(diff_abs, 2),
            is_below_average=(my_val < avg_val),
            position=position,
            total_banks=total,
            deviation_threshold=self._classify(diff_abs),
            extra=extra,
        )

    #  Классификация 
    @staticmethod
    def _deviation_level(val: float) -> str:
        # Уровень банка по отраслевым порогам (используется LLM дословно)
        if val < 0.5:
            return "соответствует норме"
        elif val < 0.8:
            return "приближается к пороговому уровню"
        elif val < 0.96:
            return "превышает пороговый уровень"
        return "критически превышает допустимый порог"

    @staticmethod
    def _magnitude_label(diff: float, my_val: float, avg_val: float) -> str:
        # Нейтральная числовая метка: «на 67% ниже среднего»
        direction = "ниже" if my_val < avg_val else "выше"
        if abs(diff) < 0.5:
            return f"на уровне среднего"
        return f"на {diff:.0f}% {direction} среднего"

    @staticmethod
    def _classify(diff: float) -> str:
        # Классификация отклонения: незначительное / среднее / существенное
        if diff < THRESHOLD_INSIGNIFICANT:
            return DeviationThreshold.INSIGNIFICANT.value
        if diff < THRESHOLD_MODERATE:
            return DeviationThreshold.MODERATE.value
        return DeviationThreshold.SIGNIFICANT.value

    # Расчёты

    @staticmethod
    def _detect_outliers(banks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Аномалии по методу IQR: значения выше Q3 + 1.5 * IQR
        values = [float(b["value"]) for b in banks]
        if len(values) < 4:
            return []
        s = sorted(values)
        n = len(s)
        q1, q3 = s[n // 4], s[(3 * n) // 4]
        iqr = q3 - q1
        if iqr == 0:
            return []
        fence = q3 + IQR_MULT * iqr
        return [{"label": b["label"], "value": float(b["value"])}
                for b in banks if float(b["value"]) > fence]

    @staticmethod
    def _adjusted_average(
        values: List[float], outliers: List[Dict[str, Any]]
    ) -> Optional[float]:
        # Среднее без учёта аномалий
        if not outliers:
            return None
        outlier_vals = {round(o["value"], 6) for o in outliers}
        clean = [v for v in values if round(v, 6) not in outlier_vals]
        return float(statistics.mean(clean)) if clean else None

    # ── Поиск и агрегация ──────────────────────────────────────────────────

    @staticmethod
    def _find_my_bank(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # Ищем элемент с label «Мой банк» (регистронезависимо)
        for item in series:
            if any(kw in str(item.get("label", "")).lower() for kw in MY_BANK_KEYWORDS):
                return item
        return None

    @staticmethod
    def _other_banks(series: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Все банки кроме «Мой банк» и строки «Среднее»
        skip = MY_BANK_KEYWORDS + AVERAGE_KEYWORDS
        return [
            {"label": item.get("label", ""), "value": float(item["value"])}
            for item in series
            if not any(kw in str(item.get("label", "")).lower() for kw in skip)
            and isinstance(item.get("value"), (int, float))
        ]

    @staticmethod
    def _calculate_average(series: List[Dict[str, Any]]) -> float:
        # Считаем среднее самостоятельно если не передано в данных
        skip = MY_BANK_KEYWORDS + AVERAGE_KEYWORDS
        values = [
            float(item["value"]) for item in series
            if not any(kw in str(item.get("label", "")).lower() for kw in skip)
            and isinstance(item.get("value"), (int, float))
        ]
        if not values:
            raise ValueError("Нет числовых данных для расчёта среднего")
        return statistics.mean(values)

    @staticmethod
    def _calculate_position(
        series: List[Dict[str, Any]], my_val: float
    ) -> Tuple[Optional[int], Optional[int]]:
        # Место банка в рейтинге по возрастанию (меньше потерь = лучше)
        values = [
            float(item["value"]) for item in series
            if not any(kw in str(item.get("label", "")).lower() for kw in AVERAGE_KEYWORDS)
            and isinstance(item.get("value"), (int, float))
        ]
        if not values:
            return None, None
        ranked = sorted(values)
        for i, v in enumerate(ranked, start=1):
            if abs(v - my_val) < 1e-6:
                return i, len(ranked)
        return None, len(ranked)

    # Форматирование для текста 
    @staticmethod
    def _fmt_ru(val: float, decimals: int = 4) -> str:
        # Число в русском формате: 0.3355 → "0,3355"
        return f"{val:.{decimals}f}".rstrip('0').rstrip('.').replace(".", ",")