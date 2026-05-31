from typing import Dict, Any, List, Optional

from src.models.output_models import MetricCalculations


#  Ключевые слова для поиска строк в series 
MY_BANK_KEYWORDS     = ("мой банк", "my bank", "мой_банк")
CLUSTER_AVG_KEYWORDS = ("среднее по кластеру", "среднее", "average", "mean")

# Пороги классификации сценариев (в процентных пунктах) 
#
#   Выведены из анализа 5 реальных эталонов Орикс:
#
#   Банк 1: diff = −3.8 п.п.  → «соответствует»
#   Банк 5: diff = −2.2 п.п.  → «соответствует»
#   Банк 3: diff = −11.3 п.п. → «существенные отклонения»
#   Банк 2: diff = −14.2 п.п. → «весьма существенные отклонения»
#   Банк 4: diff = +15.4 п.п. → «выше среднего»
#
#   Правила (по модулю отклонения):
#   «соответствует»                — |diff| < 5 п.п.
#   «существенные отклонения»      — 5 ≤ |diff| < 13 п.п. (только вниз)
#   «весьма существенные»          — |diff| ≥ 13 п.п. (только вниз)
#   «выше среднего»                — diff > 5 п.п. (банк выше кластера)

THRESHOLD_INSIGNIFICANT   = 5.0   # п.п. — предел «незначительных»
THRESHOLD_VERY_SIGNIFICANT = 13.0  # п.п. — предел «весьма существенных»

#Готовые блоки текста — вставляются LLM дословно 

_BODY_NEGATIVE = (
    "Рекомендуется дополнительно проанализировать факторы, влияющие на снижение "
    "общего уровня возмещений, такие как: организация работы с дебиторской "
    "задолженностью, наличие программ страхования по отдельным рискам. "
    "Дополнительно необходимо проанализировать эффективность процесса регистрации "
    "возмещений в базе потерь: информирование со стороны подразделений в адрес "
    "операционных рисков о фактах полученных банком возмещений, полноту и "
    "регулярность мониторинга счетов бухгалтерского учета, на которых отражаются "
    "потери. Отдельно стоит обратить внимание на сроки получения возмещений и "
    "своевременность их отражения в базе. Возможно, что отклонения также обусловлены "
    "особенностями бизнес-модели, спецификой клиентской базы и как следствие — "
    "спецификой регистрируемых потерь, по которым отсутствует возмещение."
)

_BODY_CORRESPONDS = (
    "Так, процессы работы над возмещением потерь в подразделениях вашего банка "
    "в целом соответствуют среднеотраслевым практикам. Информация о полученных "
    "возмещениях своевременно и в полной мере отражается в базе потерь."
)

_BODY_ABOVE = (
    "Это может свидетельствовать о высокой эффективности процесса выявления "
    "возмещений и их отражения в базе потерь. Вероятно, подразделения вашего банка "
    "проводят более активную работу над получением возмещений, что положительным "
    "образом сказывается на величине чистых потерь. С высокой долей вероятности "
    "можно утверждать, что со стороны операционных рисков также выстроена работа "
    "по регулярному получению информации о возмещениях и их своевременному "
    "отражению в базе потерь. Для подтверждения вывода об эффективности работы "
    "с возмещениями рекомендуем проверить значение показателя за несколько "
    "периодов и исключить влияние крупных единичных кейсов с возмещенными потерями."
)


class Metric4Calculator:

    METRIC_TYPE = "recovery_level"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        # 1. Извлекаем данные банка и кластера 

        my_bank_entry = self._find_entry(series, MY_BANK_KEYWORDS)
        if my_bank_entry is None:
            raise ValueError("Запись 'Мой банк' не найдена в series")

        cluster_entry = self._find_entry(series, CLUSTER_AVG_KEYWORDS, exclude=MY_BANK_KEYWORDS)
        if cluster_entry is None:
            raise ValueError("Запись 'Среднее по кластеру' не найдена в series")

        my_recovery  = float(my_bank_entry["self"])
        cluster_avg  = float(cluster_entry["self"])

        #  2. Отклонение в процентных пунктах
        diff_signed = my_recovery - cluster_avg
        diff_abs    = abs(diff_signed)

        # Округляем до 1 д.п. — именно это значение входит в текст вердикта
        diff_abs_display = round(diff_abs, 1)

        # 3. Классификация сценария 

        scenario_label = self._classify_scenario(diff_signed, diff_abs)

        # 4. Форматируем период для вставки в текст
        #      "2025Q3" → "Q3 2025"

        period_display = self._format_period(period)

        # 5. Готовые предложения для LLM 
        representativeness_pct = data.get("representativeness", 62)

        opening_sentence = self._build_opening(
            scenario_label, diff_abs_display, period_display
        )

        body_sentence = self._build_body(scenario_label)

        footer_sentence = (
            f"Выводы сделаны на достаточно репрезентативных данных: "
            f"{representativeness_pct}% банков загрузили в ОРИКС данные за отчетный период."
        )

        # 6. Собираем extra 
        extra: Dict[str, Any] = {
            # Сценарий
            "scenario_label": scenario_label,

            # Числовые показатели
            "my_bank_recovery":  round(my_recovery, 3),
            "cluster_avg":       round(cluster_avg, 3),
            "diff_signed":       round(diff_signed, 3),
            "diff_abs":          diff_abs_display,
            "is_above_average":  diff_signed > 0,

            # Репрезентативность
            "representativeness_pct": representativeness_pct,

            # Готовые предложения — LLM собирает вердикт из них
            "opening_sentence": opening_sentence,
            "body_sentence":    body_sentence,
            "footer_sentence":  footer_sentence,
        }

        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=round(my_recovery, 3),
            cluster_avg_value=round(cluster_avg, 3),
            # difference_percent здесь — абсолютное отклонение в п.п.
            # (аналогично total_deviation в Metric 3)
            difference_percent=diff_abs_display,
            is_below_average=(diff_signed < 0),
            position=0,
            total_banks=0,
            deviation_threshold=scenario_label,
            extra=extra,
        )

    #  Классификация сценария
    @staticmethod
    def _classify_scenario(diff_signed: float, diff_abs: float) -> str:
        # Банк выше кластера на значимую величину → «выше среднего»
        if diff_signed > THRESHOLD_INSIGNIFICANT:
            return "выше среднего"

        # Отклонение незначительное (в любую сторону) → «соответствует»
        if diff_abs < THRESHOLD_INSIGNIFICANT:
            return "соответствует"

        # Банк ниже кластера: различаем степень серьёзности
        if diff_abs >= THRESHOLD_VERY_SIGNIFICANT:
            return "весьма существенные отклонения"

        return "существенные отклонения"

    # Строим готовые предложения

    @staticmethod
    def _build_opening(scenario: str, diff_abs: float, period: str) -> str:
        if scenario == "соответствует":
            return (
                f"Уровень возмещений прямых потерь в вашем банке в {period} в целом "
                f"соответствует среднему значению по всем банкам, что свидетельствует "
                f"об отсутствии явно выраженных проблем или аномалий в сборе данных "
                f"о возмещениях в вашем банке."
            )
        if scenario == "выше среднего":
            return (
                f"Показатель возмещения прямых потерь в вашем банке в {period} "
                f"на {diff_abs} п.п. выше среднего значения по всем банкам."
            )
        if scenario == "весьма существенные отклонения":
            return (
                f"Зафиксированы весьма существенные негативные отклонения уровня "
                f"возмещений прямых потерь в вашем банке — на {diff_abs} п.п. ниже "
                f"среднего значения по всем банкам в {period}."
            )
        # «существенные отклонения»
        return (
            f"Зафиксированы существенные отклонения уровня возмещений прямых потерь "
            f"в вашем банке — на {diff_abs} п.п. ниже среднего значения по всем "
            f"банкам в {period}."
        )

    @staticmethod
    def _build_body(scenario: str) -> str:
        if scenario == "соответствует":
            return _BODY_CORRESPONDS
        if scenario == "выше среднего":
            return _BODY_ABOVE
        # «существенные» и «весьма существенные» используют один и тот же блок
        return _BODY_NEGATIVE

    # Вспомогательные методы 
    @staticmethod
    def _find_entry(
        series: List[Dict[str, Any]],
        keywords: tuple,
        exclude: Optional[tuple] = None,
    ) -> Optional[Dict[str, Any]]:
        """Ищет первую запись в series, чей label содержит одно из keywords.
        Если передан exclude — пропускает записи, чей label содержит любое из них.
        """
        for item in series:
            label_lower = str(item.get("label", "")).lower()
            if exclude and any(kw in label_lower for kw in exclude):
                continue
            if any(kw in label_lower for kw in keywords):
                val = item.get("self")
                if val is None:
                    raise ValueError(
                        f"Отсутствует поле 'self' в записи '{item.get('label')}'"
                    )
                if not isinstance(val, (int, float)):
                    raise ValueError(
                        f"Поле 'self' должно быть числом в записи '{item.get('label')}': {val}"
                    )
                return item
        return None

    @staticmethod
    def _format_period(period: str) -> str:
        # "2025Q3" → "Q3 2025"
        if "Q" in period:
            parts = period.split("Q")
            if len(parts) == 2 and parts[0].isdigit():
                return f"Q{parts[1]} {parts[0]}"
        return period
