from typing import Dict, Any, List, Tuple, Optional

from src.models.output_models import MetricCalculations


# ── Пороги классификации сценариев ────────────────────────────────────────────
# Выведены из анализа 5 реальных эталонов Орикс:
#
#   Банк 2: total=23.1пп, max_single=8.7пп  → «незначительные отклонения»
#   Банк 1: total=33.3пп, max_single=16.6пп → «расхождения»
#   Банк 3: total=31.6пп, max_single=15.8пп → «расхождения»
#   Банк 4: total=32.8пп, max_single=15.8пп → «расхождения»
#   Банк 5: total=147.4пп, max/min бакеты не совпадают → «кардинально отличается»
#
# Правила:
#   «незначительные отклонения»  — total < 25пп И ни один бакет >= 10пп
#                                    И бакеты max/min совпадают с рынком
#   «расхождения»                — max/min совпадают И (есть бакет >= 10пп
#                                    ИЛИ total >= 25пп) И total < 100пп
#   «кардинально отличается»     — max/min НЕ совпадают ИЛИ total >= 100пп

THRESHOLD_TOTAL_INSIGNIFICANT = 25.0   # пп — предел «незначительных»
THRESHOLD_SINGLE_SIGNIFICANT  = 10.0   # пп — отклонение одного бакета «> 10%»
THRESHOLD_TOTAL_DRASTIC       = 100.0  # пп — предел «кардинально»


class Metric3Calculator:

    METRIC_TYPE = "loss_buckets"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        # Извлекаем бакеты: label, self (доля банка %), rest (доля рынка %)
        buckets = self._extract_buckets(series)

        if len(buckets) < 2:
            raise ValueError(
                f"Слишком мало бакетов: {len(buckets)}. Ожидается минимум 2."
            )

        labels   = [b["label"] for b in buckets]
        self_pct = [b["self"]  for b in buckets]
        rest_pct = [b["rest"]  for b in buckets]

        # 1. Отклонения по каждому бакету 

        # Знаковое и абсолютное отклонение для каждого бакета
        diffs_signed = [s - r for s, r in zip(self_pct, rest_pct)]
        diffs_abs    = [abs(d) for d in diffs_signed]

        # Суммарное отклонение = сумма модулей по всем бакетам
        # Именно эту цифру Орикс публикует в вердикте: «сумма отклонений составляет X п.п.»
        total_deviation = round(sum(diffs_abs), 1)

        # 2. Бакет с максимальным отклонением 

        max_diff_idx    = diffs_abs.index(max(diffs_abs))
        max_diff_bucket = labels[max_diff_idx]
        max_diff_abs    = round(diffs_abs[max_diff_idx], 1)
        max_diff_signed = round(diffs_signed[max_diff_idx], 1)

        # Флаг: есть ли хотя бы один бакет с отклонением >= 10пп
        any_diff_over_10 = any(d >= THRESHOLD_SINGLE_SIGNIFICANT for d in diffs_abs)

        # 3. Бакеты с максимальной и минимальной долей (банк и рынок) 

        # Бакет с наибольшей долей в портфеле банка
        max_bank_idx   = self_pct.index(max(self_pct))
        max_bank_label = labels[max_bank_idx]
        max_bank_pct   = round(self_pct[max_bank_idx], 3)

        # Бакет с наименьшей долей в портфеле банка
        # Если несколько бакетов с одинаковым минимумом (например, 0%) — берём последний,
        # так как он даёт более сильный аналитический вывод (крупный диапазон без потерь)
        min_val        = min(self_pct)
        min_bank_idx   = len(self_pct) - 1 - self_pct[::-1].index(min_val)
        min_bank_label = labels[min_bank_idx]
        min_bank_pct   = round(self_pct[min_bank_idx], 3)

        # Бакет с наибольшей долей в среднем по рынку
        max_rest_idx   = rest_pct.index(max(rest_pct))
        max_rest_label = labels[max_rest_idx]
        max_rest_pct   = round(rest_pct[max_rest_idx], 3)

        # Бакет с наименьшей долей в среднем по рынку
        min_rest_idx   = rest_pct.index(min(rest_pct))
        min_rest_label = labels[min_rest_idx]
        min_rest_pct   = round(rest_pct[min_rest_idx], 3)

        # Совпадают ли бакеты максимума/минимума у банка и рынка
        max_buckets_match = (max_bank_label == max_rest_label)
        min_buckets_match = (min_bank_label == min_rest_label)

        # 4. Классификация сценария 

        scenario_label = self._classify_scenario(
            total_deviation, any_diff_over_10,
            max_buckets_match, min_buckets_match
        )

        # 5. Готовые предложения для LLM (по сценариям) 

        # Предложение о совпадении бакетов max/min (используется в сценариях
        # «незначительные» и «расхождения» когда max и min совпадают)
        if max_buckets_match and min_buckets_match:
            buckets_match_sentence = (
                f"Диапазоны, на которые приходится максимальный и минимальный объём "
                f"прямых потерь в вашем банке, совпадают с теми, на которые приходится "
                f"максимальный/минимальный объём в среднем по всем банкам."
            )
        elif max_buckets_match and not min_buckets_match:
            buckets_match_sentence = (
                f"Диапазон с максимальным объёмом прямых потерь в вашем банке "
                f"совпадает со средним по всем банкам, однако минимальный объём "
                f"потерь сосредоточен в разных бакетах."
            )
        elif not max_buckets_match and min_buckets_match:
            buckets_match_sentence = (
                f"Диапазон с минимальным объёмом прямых потерь в вашем банке "
                f"совпадает со средним по всем банкам, однако максимальный объём "
                f"потерь сосредоточен в разных бакетах."
            )
        else:
            buckets_match_sentence = (
                f"Диапазоны, на которые приходится максимальный и минимальный объём "
                f"прямых потерь в вашем банке, не совпадают с аналогичными диапазонами "
                f"в среднем по всем банкам."
            )

        # Предложение об итоговой сумме отклонений (используется во всех сценариях)
        total_deviation_sentence = (
            f"Сумма отклонений по всем бакетам составляет {total_deviation} п.п. "
            f"от среднего значения по всем банкам."
        )

        # Готовое предложение о максимальном отклонении
        # Убираем «+» из метки бакета — «суммой от» уже подразумевает ≥
        bucket_label_clean = max_diff_bucket.rstrip('+')

        if max_diff_abs >= THRESHOLD_SINGLE_SIGNIFICANT:
            max_diff_sentence = (
                f"Наиболее значительное отклонение данных вашего банка от среднего "
                f"— {max_diff_abs} п.п. общего объёма потерь — приходится на бакет "
                f"суммой от {bucket_label_clean} тыс. руб."
            )
        else:
            # Для «незначительных отклонений» — включаем факт что ни один бакет не превышает 10 п.п.
            max_diff_sentence = (
                f"В каждом бакете отклонения не более 10 п.п., при этом максимальное "
                f"отклонение наблюдается в бакете суммой от "
                f"{bucket_label_clean} тыс. руб. ({max_diff_abs} п.п.)."
            )

        # 6. Дополнительные поля для сценария «кардинально отличается» 

        # Наибольший бакет, в котором у банка есть ненулевые потери
        bank_max_effective_label = self._find_max_effective_bucket(labels, self_pct)

        # Бакеты, где у банка доля = 0 (полное отсутствие потерь)
        zero_buckets = [labels[i] for i, v in enumerate(self_pct) if v == 0.0]
        has_zero_buckets = len(zero_buckets) > 0

        # Готовое предложение о концентрации (для «кардинально»)
        if scenario_label == "кардинально отличается":
            concentration_sentence = (
                f"Суммы понесённых потерь вашего банка фактически не превышают "
                f"{bank_max_effective_label} тыс. руб.: основной объём сосредоточен "
                f"в бакете {max_bank_label} тыс. руб. ({max_bank_pct:.1f}%), "
                f"тогда как в среднем по всем банкам основной объём потерь "
                f"концентрируется в бакете {max_rest_label} тыс. руб."
            ) if has_zero_buckets else (
                f"Основной объём потерь вашего банка сосредоточен в бакете "
                f"{max_bank_label} тыс. руб. ({max_bank_pct:.1f}%), тогда как "
                f"в среднем по всем банкам основной объём концентрируется в бакете "
                f"{max_rest_label} тыс. руб."
            )
            # Предложение о минимальном бакете (только когда min не совпадает)
            min_mismatch_sentence = (
                f"Минимальный объём прямых потерь вашего банка сосредоточен в бакете "
                f"{min_bank_label} тыс. руб., тогда как минимальный объём в среднем "
                f"по всем банкам — в диапазоне {min_rest_label} тыс. руб."
            ) if not min_buckets_match else ""
        else:
            concentration_sentence = ""
            min_mismatch_sentence = ""

        #7. Собираем extra 

        extra: Dict[str, Any] = {
            # Сценарий
            "scenario_label": scenario_label,

            # Суммарное отклонение
            "total_deviation": total_deviation,
            "total_deviation_sentence": total_deviation_sentence,

            # Бакет с максимальным отклонением
            "max_diff_bucket": max_diff_bucket,
            "max_diff_abs": max_diff_abs,
            "max_diff_signed": max_diff_signed,
            "any_diff_over_10": any_diff_over_10,
            "max_diff_sentence": max_diff_sentence,

            # Бакеты концентрации (банк)
            "max_bank_bucket": max_bank_label,
            "max_bank_pct": max_bank_pct,
            "min_bank_bucket": min_bank_label,
            "min_bank_pct": min_bank_pct,

            # Бакеты концентрации (рынок)
            "max_rest_bucket": max_rest_label,
            "max_rest_pct": max_rest_pct,
            "min_rest_bucket": min_rest_label,
            "min_rest_pct": min_rest_pct,

            # Совпадение бакетов max/min
            "max_buckets_match": max_buckets_match,
            "min_buckets_match": min_buckets_match,
            "buckets_match_sentence": buckets_match_sentence,

            # Для сценария «кардинально отличается»
            "has_zero_buckets": has_zero_buckets,
            "zero_buckets": zero_buckets,
            "bank_max_effective_bucket": bank_max_effective_label,
            "concentration_sentence": concentration_sentence,
            "min_mismatch_sentence": min_mismatch_sentence,

            # Детальные данные по каждому бакету — для промпта и валидатора
            "bucket_details": [
                {
                    "label":        labels[i],
                    "self_pct":     round(self_pct[i], 3),
                    "rest_pct":     round(rest_pct[i], 3),
                    "diff_signed":  round(diffs_signed[i], 3),
                    "diff_abs":     round(diffs_abs[i], 3),
                }
                for i in range(len(labels))
            ],
        }

        # my_bank_value  — доля потерь в главном бакете банка (наибольшая концентрация)
        # cluster_avg   — доля рынка в том же бакете (для сравнения)
        # difference_percent — суммарное отклонение (главная цифра вердикта)
        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=max_bank_pct,
            cluster_avg_value=rest_pct[max_bank_idx],
            difference_percent=total_deviation,
            is_below_average=(total_deviation < THRESHOLD_TOTAL_INSIGNIFICANT),
            position=0,
            total_banks=0,
            deviation_threshold=scenario_label,
            extra=extra,
        )

    # Извлечение данных 

    @staticmethod
    def _extract_buckets(series: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Для Метрики 3 каждый элемент — бакет потерь с полями label, self, rest
        result = []
        for item in series:
            label = item.get("label")
            s = item.get("self")
            r = item.get("rest")
            if label is None:
                raise ValueError(f"Отсутствует поле label в элементе: {item}")
            if s is None or r is None:
                raise ValueError(
                    f"Отсутствуют поля self/rest в бакете '{label}': {item}"
                )
            if not isinstance(s, (int, float)) or not isinstance(r, (int, float)):
                raise ValueError(
                    f"self и rest должны быть числами в бакете '{label}': {item}"
                )
            result.append({
                "label": str(label),
                "self":  float(s),
                "rest":  float(r),
            })
        return result

    # Классификация сценария 

    @staticmethod
    def _classify_scenario(
        total_deviation: float,
        any_diff_over_10: bool,
        max_buckets_match: bool,
        min_buckets_match: bool,
    ) -> str:
        # «кардинально отличается»:
        #   — бакеты max/min НЕ совпадают, ИЛИ суммарное отклонение >= 100пп
        #   (Банк 5: max/min не совпадают, total=147.4пп → кардинально)
        if not max_buckets_match or not min_buckets_match or total_deviation >= THRESHOLD_TOTAL_DRASTIC:
            return "кардинально отличается"

        # «незначительные отклонения»:
        #   — суммарное отклонение < 25пп И ни один бакет не отклоняется на >= 10пп
        #   (Банк 2: total=23.1пп, max_single=8.7пп → незначительные)
        if total_deviation < THRESHOLD_TOTAL_INSIGNIFICANT and not any_diff_over_10:
            return "незначительные отклонения"

        # «расхождения» — всё остальное
        #   (Банки 1, 3, 4: total=31–33пп, max_single=15–17пп → расхождения)
        return "расхождения"

    # Вспомогательные методы

    @staticmethod
    def _find_max_effective_bucket(
        labels: List[str], self_pct: List[float]
    ) -> str:
        # Находим самый крупный бакет (последний в списке),
        # в котором у банка есть ненулевые потери.
        # Используется для сценария «кардинально» чтобы описать
        # фактический потолок потерь банка.
        last_nonzero = None
        for label, pct in zip(labels, self_pct):
            if pct > 0:
                last_nonzero = label
        return last_nonzero or labels[-1]
