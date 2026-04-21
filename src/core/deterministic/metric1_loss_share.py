# src/core/deterministic/metric1_loss_share.py

from typing import Dict, Any, List, Optional, Tuple
import statistics

from src.models.output_models import MetricCalculations
from src.models.enums import DeviationThreshold


MY_BANK_KEYWORDS = ("мой банк", "my bank", "мой_банк")
AVERAGE_KEYWORDS = ("среднее", "average", "mean")

# пороги из эталонов Орикс
THRESHOLD_INSIGNIFICANT = 10.0
THRESHOLD_MODERATE = 30.0


class Metric1Calculator:

    METRIC_TYPE = "loss_share"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        my_bank = self._find_my_bank(series)
        if my_bank is None:
            raise ValueError("Мой банк не найден в данных")

        my_val = my_bank.get("value")
        if my_val is None:
            raise ValueError("У Мой банк нет поля value")

        # берём среднее из данных или считаем сами
        avg_val = data.get("avg") or self._calculate_average(series)

        if avg_val == 0:
            raise ValueError("Среднее равно 0, деление невозможно")

        diff_pct = ((my_val - avg_val) / avg_val) * 100.0
        threshold = self._classify(abs(diff_pct))
        position, total = self._calculate_position(series, my_val)

        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=round(float(my_val), 4),
            cluster_avg_value=round(float(avg_val), 4),
            difference_percent=round(diff_pct, 1),
            is_below_average=(my_val < avg_val),
            position=position,
            total_banks=total,
            deviation_threshold=threshold,
            extra={
                "representativeness_pct": data.get("representativeness", 62),
                "deviation_direction": "ниже" if my_val < avg_val else "выше",
            }
        )

    @staticmethod
    def _find_my_bank(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for item in series:
            label = str(item.get("label", "")).lower()
            if any(kw in label for kw in MY_BANK_KEYWORDS):
                return item
        return None

    @staticmethod
    def _calculate_average(series: List[Dict[str, Any]]) -> float:
        # считаем среднее только по банкам, без Мой банк и Среднее по кластеру
        values = []
        for item in series:
            label = str(item.get("label", "")).lower()
            val = item.get("value")
            if any(kw in label for kw in MY_BANK_KEYWORDS + AVERAGE_KEYWORDS):
                continue
            if isinstance(val, (int, float)):
                values.append(float(val))
        if not values:
            raise ValueError("Нет данных для расчёта среднего")
        return statistics.mean(values)

    @staticmethod
    def _classify(abs_diff: float) -> str:
        if abs_diff < THRESHOLD_INSIGNIFICANT:
            return DeviationThreshold.INSIGNIFICANT.value
        if abs_diff < THRESHOLD_MODERATE:
            return DeviationThreshold.MODERATE.value
        return DeviationThreshold.SIGNIFICANT.value

    @staticmethod
    def _calculate_position(
        series: List[Dict[str, Any]],
        my_val: float
    ) -> Tuple[Optional[int], Optional[int]]:
        # место в рейтинге по возрастанию (меньше потерь = лучше)
        values = []
        for item in series:
            label = str(item.get("label", "")).lower()
            val = item.get("value")
            if any(kw in label for kw in AVERAGE_KEYWORDS):
                continue
            if isinstance(val, (int, float)):
                values.append(float(val))

        if not values:
            return None, None

        sorted_vals = sorted(values)
        total = len(sorted_vals)
        for i, val in enumerate(sorted_vals, start=1):
            if abs(val - my_val) < 1e-6:
                return i, total
        return None, total