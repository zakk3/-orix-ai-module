from typing import Dict, Any, List, Optional, Tuple
import statistics
import random

from src.models.output_models import MetricCalculations
from src.models.enums import DeviationThreshold


# Ключевые слова для определения строки «Мой банк» и строки «Среднее» в series
MY_BANK_KEYWORDS = ("мой банк", "my bank", "мой_банк")
AVERAGE_KEYWORDS = ("среднее", "average", "mean")

# Пороги для классификации отклонения в процентах
THRESHOLD_INSIGNIFICANT = 10.0
THRESHOLD_MODERATE = 30.0

# Коэффициент для определения выбросов по методу IQR
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

        # Выбросы только среди других банков; скорректированное среднее без них
        outliers = self._detect_outliers(other_banks)
        adjusted_avg = self._adjusted_average(other_values, outliers)

        # Форматированные строки для предложений
        period_display  = self._period_display(period)
        magnitude_label = self._magnitude_label(diff_abs, my_val, avg_val)
        bank_fmt        = self._fmt_ru(float(my_val), 2)
        avg_fmt         = self._fmt_ru(float(avg_val), 2)
        diff_fmt        = self._fmt_ru(diff_abs, 1)
        median_fmt      = self._fmt_ru(median_value, 2)

        # Строим готовые предложения
        opening_sentence = self._build_opening_sentence(
            period_display, bank_fmt, avg_fmt, diff_fmt, magnitude_label, diff_abs
        )

        outlier_sentence = ""
        if outliers:
            top = max(outliers, key=lambda b: b["value"])
            o_fmt = self._fmt_ru(float(top["value"]), 2)
            a_fmt = self._fmt_ru(adjusted_avg, 2) if adjusted_avg is not None else "—"
            outlier_sentence = self._build_outlier_sentence(top["label"], o_fmt, a_fmt)

        median_sentence   = self._build_median_sentence(
            median_fmt,
            "выше" if float(my_val) >= median_value else "ниже"
        )
        position_sentence = self._build_position_sentence(position, total)
        footer_sentence   = self._build_footer_sentence(
            data.get("representativeness", 62)
        )

        # Собираем дополнительные поля
        extra: Dict[str, Any] = {
            "period_display":          period_display,
            "representativeness_pct":  data.get("representativeness", 62),
            "deviation_direction":     "ниже" if my_val < avg_val else "выше",
            # deviation_level используется только для внутренней калибровки тона LLM,
            # не для дословного воспроизведения в выводе
            "deviation_level":         self._deviation_level(my_val),
            "magnitude_label":         magnitude_label,
            "median_value":            round(median_value, 4),
            "median_value_fmt":        median_fmt,
            "my_bank_vs_median":       "ниже" if float(my_val) < median_value else "выше",
            "has_outliers":            bool(outliers),
            # Готовые предложения
            "opening_sentence":        opening_sentence,
            "outlier_sentence":        outlier_sentence,
            "median_sentence":         median_sentence,
            "position_sentence":       position_sentence,
            "footer_sentence":         footer_sentence,
            "conclusion_sentence":     self._build_conclusion_sentence(
                float(my_val), float(avg_val), self._deviation_level(my_val)
            ),
        }

        # Если есть выбросы — добавляем информацию о самом крупном
        if outliers:
            top = max(outliers, key=lambda b: b["value"])
            extra.update({
                "outlier_label":       top["label"],
                "outlier_value":       round(float(top["value"]), 4),
                "outlier_value_fmt":   self._fmt_ru(top["value"], 2),
                "outliers_count":      len(outliers),
            })
            if adjusted_avg is not None:
                extra["adjusted_avg"]     = round(adjusted_avg, 4)
                extra["adjusted_avg_fmt"] = self._fmt_ru(adjusted_avg, 2)

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

    # ── Классификация ─────────────────────────────────────────────────────────

    @staticmethod
    def _deviation_level(val: float) -> str:
        """Уровень банка по отраслевым порогам — используется только для калибровки
        тона LLM, не для дословного воспроизведения в итоговом тексте."""
        if val < 0.5:
            return "соответствует норме"
        elif val < 0.8:
            return "приближается к пороговому уровню"
        elif val < 0.96:
            return "превышает пороговый уровень"
        return "критически превышает допустимый порог"

    @staticmethod
    def _magnitude_label(diff: float, my_val: float, avg_val: float) -> str:
        """Оценочное слово для отклонения — вставляется органично в открывающее предложение."""
        direction = "ниже" if my_val < avg_val else "выше"
        if diff < 15:
            return f"{direction} среднего"
        elif diff < 40:
            return f"несколько {direction} среднего"
        return f"существенно {direction} среднего"

    @staticmethod
    def _classify(diff: float) -> str:
        """Классификация отклонения: незначительное / среднее / существенное."""
        if diff < THRESHOLD_INSIGNIFICANT:
            return DeviationThreshold.INSIGNIFICANT.value
        if diff < THRESHOLD_MODERATE:
            return DeviationThreshold.MODERATE.value
        return DeviationThreshold.SIGNIFICANT.value

    # ── Строители готовых предложений ─────────────────────────────────────────

    @staticmethod
    def _period_display(period: str) -> str:
        """'2025Q3' → 'Q3 2025'"""
        if len(period) >= 6 and period[4] == 'Q':
            return f"Q{period[5]} {period[:4]}"
        return period

    @staticmethod
    def _build_opening_sentence(
        period_display: str, bank_fmt: str, avg_fmt: str,
        diff_fmt: str, magnitude_label: str, diff_abs: float
    ) -> str:
        # ВАЖНО: дата («По итогам Q3 2025») сюда НЕ включается — она вставляется
        # отдельно, ДОСЛОВНО, перед этим предложением. Иначе LLM воспринимает
        # дату как часть текста для перефразирования и заменяет «Q3 2025»
        # на «третий квартал две тысячи двадцать пятого года».
        #
        # НЕСКОЛЬКО вариантов шаблона — выбор случайный при каждом вызове.
        # Если бы шаблон был один, при повторных запросах с одними и теми же
        # входными данными LLM видел бы один и тот же текст для перефразирования
        # и мог бы просто копировать его вместо реальной синонимической замены.
        if diff_abs < THRESHOLD_INSIGNIFICANT:
            variants = [
                f"показатель чистых потерь вашего банка относительно "
                f"бизнес-индикатора составил {bank_fmt}%, что в целом "
                f"соответствует среднему значению по кластеру ({avg_fmt}%): "
                f"разница составляет {diff_fmt}%.",
                f"значение чистых потерь вашего банка по отношению к "
                f"бизнес-индикатору достигло {bank_fmt}%, что практически "
                f"совпадает со средним показателем по кластеру ({avg_fmt}%): "
                f"отклонение составляет {diff_fmt}%.",
                f"уровень чистых потерь вашего банка относительно "
                f"бизнес-индикатора зафиксирован на отметке {bank_fmt}%, что "
                f"фактически соответствует среднему по кластеру ({avg_fmt}%): "
                f"разница составляет {diff_fmt}%.",
            ]
            return random.choice(variants)
        variants = [
            f"показатель чистых потерь вашего банка относительно "
            f"бизнес-индикатора составил {bank_fmt}%, что "
            f"{magnitude_label} по кластеру ({avg_fmt}%): "
            f"разница составляет {diff_fmt}%.",
            f"значение чистых потерь вашего банка по отношению к "
            f"бизнес-индикатору достигло {bank_fmt}%, что "
            f"{magnitude_label} по кластеру ({avg_fmt}%): "
            f"отклонение составляет {diff_fmt}%.",
            f"уровень чистых потерь вашего банка относительно "
            f"бизнес-индикатора зафиксирован на отметке {bank_fmt}%, что "
            f"{magnitude_label} значения по кластеру ({avg_fmt}%): "
            f"разница составляет {diff_fmt}%.",
        ]
        return random.choice(variants)

    @staticmethod
    def _build_outlier_sentence(
        outlier_label: str, outlier_fmt: str, adjusted_fmt: str
    ) -> str:
        variants = [
            f"При этом на среднее по кластеру существенное влияние оказывает "
            f"банк {outlier_label} с показателем {outlier_fmt}%: "
            f"без его учёта скорректированное среднее составляет {adjusted_fmt}%.",
            f"Стоит отметить, что банк {outlier_label} с показателем "
            f"{outlier_fmt}% существенно искажает среднее по кластеру: "
            f"без учёта этого банка скорректированное среднее равно {adjusted_fmt}%.",
            f"При этом банк {outlier_label}, показавший {outlier_fmt}%, "
            f"заметно влияет на среднее по кластеру: если его исключить, "
            f"скорректированное среднее составит {adjusted_fmt}%.",
        ]
        return random.choice(variants)

    @staticmethod
    def _build_median_sentence(median_fmt: str, above_below: str) -> str:
        variants = [
            f"Медианное значение по выборке составляет {median_fmt}% — "
            f"ваш банк расположен {above_below} медианного уровня.",
            f"Медиана по выборке равна {median_fmt}% — "
            f"ваш банк находится {above_below} медианного уровня.",
            f"По выборке медианное значение зафиксировано на уровне {median_fmt}% "
            f"— банк располагается {above_below} медианного уровня.",
        ]
        return random.choice(variants)

    @staticmethod
    def _build_position_sentence(position: Optional[int], total: Optional[int]) -> str:
        if position and total:
            variants = [
                f"По данному показателю ваш банк занимает {position}-е место "
                f"из {total} банков, предоставивших данные.",
                f"Среди {total} банков, предоставивших данные, ваш банк "
                f"занимает {position}-е место по данному показателю.",
                f"По данному показателю позиция вашего банка — {position}-е "
                f"место из {total} банков, предоставивших данные.",
            ]
            return random.choice(variants)
        return "Позиция банка в рейтинге не определена."

    @staticmethod
    def _build_footer_sentence(representativeness: int) -> str:
        return (
            f"Выводы основаны на данных {representativeness}% банков кластера, "
            f"загрузивших информацию в ОРИКС."
        )

    @staticmethod
    def _build_conclusion_sentence(my_val: float, avg_val: float, deviation_level: str) -> str:
        """Готовое предложение-заключение — перефразируется LLM, не копируется дословно."""
        if my_val < avg_val:
            if "норме" in deviation_level:
                return (
                    "В целом, банк демонстрирует низкий уровень операционных потерь "
                    "относительно среднего по рынку."
                )
            else:
                return (
                    "В целом, банк демонстрирует уровень операционных потерь ниже среднего, "
                    "однако превышение отраслевого порога требует внимания."
                )
        elif my_val > avg_val:
            if "критически" in deviation_level:
                return (
                    "В целом, банк демонстрирует критически высокий уровень операционных потерь "
                    "относительно среднего по рынку."
                )
            elif "превышает" in deviation_level:
                return (
                    "В целом, банк демонстрирует высокий уровень операционных потерь "
                    "относительно среднего по рынку."
                )
            else:
                return (
                    "В целом, банк демонстрирует уровень операционных потерь выше среднего "
                    "по рынку."
                )
        return (
            "В целом, банк демонстрирует уровень операционных потерь, "
            "сопоставимый со средним по рынку."
        )

    # ── Расчёты ───────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_outliers(banks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Выбросы по методу IQR: значения выше Q3 + 1.5 * IQR."""
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
        """Среднее без учёта выбросов."""
        if not outliers:
            return None
        outlier_vals = {round(o["value"], 6) for o in outliers}
        clean = [v for v in values if round(v, 6) not in outlier_vals]
        return float(statistics.mean(clean)) if clean else None

    # ── Поиск и агрегация ─────────────────────────────────────────────────────

    @staticmethod
    def _find_my_bank(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for item in series:
            if any(kw in str(item.get("label", "")).lower() for kw in MY_BANK_KEYWORDS):
                return item
        return None

    @staticmethod
    def _other_banks(series: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        skip = MY_BANK_KEYWORDS + AVERAGE_KEYWORDS
        return [
            {"label": item.get("label", ""), "value": float(item["value"])}
            for item in series
            if not any(kw in str(item.get("label", "")).lower() for kw in skip)
            and isinstance(item.get("value"), (int, float))
        ]

    @staticmethod
    def _calculate_average(series: List[Dict[str, Any]]) -> float:
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
        """Место банка в рейтинге по возрастанию (меньше потерь = лучше)."""
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

    # ── Форматирование ────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_ru(val: float, decimals: int = 2) -> str:
        """Число в русском формате с указанной точностью: 0.269 → '0,27' (2 знака)."""
        return f"{val:.{decimals}f}".rstrip('0').rstrip('.').replace(".", ",")
