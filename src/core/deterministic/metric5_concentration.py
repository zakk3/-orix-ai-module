from typing import Dict, Any, List

from src.models.output_models import MetricCalculations

# Порог существенного отклонения по отдельному источнику (п.п.)
THRESHOLD_SIGNIFICANT    = 10.0
# Порог сценария «значительно отличается» по максимальному отклонению (п.п.)
THRESHOLD_VERY_DIFFERENT = 25.0

# Стандартная оговорка о различиях в профиле риска — включается во все сценарии
_DISCLAIMER = (
    "Отличия в источниках потерь, возможно, свидетельствуют о различающемся "
    "профиле риска вашего банка и других банков в выбранной группе сравнения. "
    "С другой стороны, могут иметь место различия в особенностях выявления "
    "и классификации потерь."
)

# Шаблон алерта: триггерится если «Недостатки процессов» ниже кластера на ≥ 10 п.п.
_ALERT_TEMPLATE = (
    "Также стоит обратить внимание, что по источнику риска Недостатки процессов "
    "у вас зарегистрировано меньше всего потерь, что нетипично для других банков "
    "в кластере: разница составляет {diff_abs} п.п.. Целесообразно провести "
    "дополнительный анализ, чтобы убедиться в полноте выявления и качестве "
    "классификации событий по указанному источнику риска."
)


class Metric5Calculator:

    METRIC_TYPE = "concentration"

    def calculate(self, data: Dict[str, Any], period: str = "2025Q3") -> MetricCalculations:
        """Вычисляет концентрацию потерь по источникам риска и возвращает MetricCalculations."""
        series = data.get("series", [])
        if not series:
            raise ValueError("series пустой")

        # Проверяем наличие self/rest в каждой записи
        for entry in series:
            if entry.get("self") is None or entry.get("rest") is None:
                raise ValueError(f"Отсутствует self/rest в записи '{entry.get('label')}'")

        # Разности и абсолютные отклонения по каждому источнику
        diffs     = {e["label"]: e["self"] - e["rest"] for e in series}
        abs_diffs = {k: abs(v) for k, v in diffs.items()}

        # Число источников с существенным отклонением (≥ 10 п.п.)
        n_significant = sum(1 for v in abs_diffs.values() if v >= THRESHOLD_SIGNIFICANT)

        # Сортировка по убыванию доли: топ-2 у банка и у кластера
        sorted_bank    = sorted(series, key=lambda e: e["self"], reverse=True)
        sorted_cluster = sorted(series, key=lambda e: e["rest"], reverse=True)

        top2_bank        = [e["label"] for e in sorted_bank[:2]]
        top2_cluster     = [e["label"] for e in sorted_cluster[:2]]
        top2_bank_pct    = round(sum(e["self"] for e in sorted_bank[:2]), 1)
        top2_cluster_pct = round(sum(e["rest"] for e in sorted_cluster[:2]), 1)
        top2_match       = set(top2_bank) == set(top2_cluster)

        # Источник с максимальным абсолютным отклонением
        max_diff_label  = max(abs_diffs, key=abs_diffs.get)
        max_diff_abs    = round(abs_diffs[max_diff_label], 1)
        max_diff_signed = round(diffs[max_diff_label], 1)

        # Проверка триггера алерта по «Недостатки процессов»
        ned_diff             = diffs.get("Недостатки процессов", 0.0)
        has_nedostatki_alert = ned_diff <= -THRESHOLD_SIGNIFICANT
        nedostatki_diff_abs  = round(abs(ned_diff), 1) if has_nedostatki_alert else None

        # Сценарная классификация
        scenario_label = self._classify_scenario(n_significant, max_diff_abs, top2_match)

        # Готовые предложения для промпта
        opening_sentence    = self._build_opening(scenario_label, n_significant)
        top2_sentence       = self._build_top2(
            top2_bank, top2_bank_pct,
            top2_cluster, top2_cluster_pct,
            top2_match, max_diff_label, max_diff_abs, max_diff_signed,
        )
        disclaimer_sentence = _DISCLAIMER
        alert_sentence      = (
            _ALERT_TEMPLATE.format(diff_abs=nedostatki_diff_abs)
            if has_nedostatki_alert else ""
        )

        # Дополнительные поля для промпта и оценщика
        extra: Dict[str, Any] = {
            "scenario_label":       scenario_label,
            "n_significant":        n_significant,
            "top2_bank":            top2_bank,
            "top2_bank_pct":        top2_bank_pct,
            "top2_cluster":         top2_cluster,
            "top2_cluster_pct":     top2_cluster_pct,
            "top2_match":           top2_match,
            "max_diff_source":      max_diff_label,
            "max_diff_abs":         max_diff_abs,
            "max_diff_signed":      max_diff_signed,
            "has_nedostatki_alert": has_nedostatki_alert,
            "nedostatki_diff_abs":  nedostatki_diff_abs,
            "opening_sentence":     opening_sentence,
            "top2_sentence":        top2_sentence,
            "disclaimer_sentence":  disclaimer_sentence,
            "alert_sentence":       alert_sentence,
        }

        return MetricCalculations(
            metric_type=self.METRIC_TYPE,
            period=period,
            my_bank_value=top2_bank_pct,
            cluster_avg_value=top2_cluster_pct,
            difference_percent=max_diff_abs,
            is_below_average=(max_diff_signed < 0),
            position=0,
            total_banks=0,
            deviation_threshold=scenario_label,
            extra=extra,
        )

    @staticmethod
    def _classify_scenario(n_significant: int, max_diff_abs: float, top2_match: bool) -> str:
        """Определяет сценарий по числу существенных отклонений, max-diff и совпадению топ-2."""
        if n_significant == 0:
            return "идентична"
        if n_significant == 1:
            return "некоторые отличия"
        if max_diff_abs >= THRESHOLD_VERY_DIFFERENT:
            return "значительно отличается"
        if top2_match:
            return "умеренные различия"
        return "некоторые различия"

    @staticmethod
    def _build_opening(scenario: str, n_significant: int) -> str:
        """Вступительное предложение: сценарная фраза + счётчик источников с отклонением."""
        scenario_phrase = {
            "идентична":              "практически идентична средней структуре",
            "некоторые отличия":      "характеризуется некоторыми отличиями от средней картины",
            "некоторые различия":     "характеризуется некоторыми различиями по сравнению со структурой",
            "умеренные различия":     "отличается от структуры",
            "значительно отличается": "значительно отличается от средней картины",
        }.get(scenario, "отличается от структуры")

        opening = f"Структура источников риска в вашем банке {scenario_phrase} по другим банкам."

        if n_significant == 0:
            count_phrase = "Существенных отклонений ни по одному из источников риска не зафиксировано."
        elif n_significant == 1:
            count_phrase = (
                "Лишь в 1 из 4 источников риска зафиксировано существенное "
                "- более 10 п.п. - отклонение от средних значений."
            )
        else:
            count_phrase = (
                f"В {n_significant} из 4 источников риска зафиксировано существенное "
                f"- более 10 п.п. - отклонение от средних значений."
            )

        return f"{opening} {count_phrase}"

    @staticmethod
    def _build_top2(
        top2_bank: List[str], top2_bank_pct: float,
        top2_cluster: List[str], top2_cluster_pct: float,
        top2_match: bool,
        max_diff_label: str, max_diff_abs: float, max_diff_signed: float,
    ) -> str:
        """Предложение о топ-2 источниках: совпадение/несовпадение с кластером и max-diff."""
        bank_pct_int    = round(top2_bank_pct)
        cluster_pct_int = round(top2_cluster_pct)

        if top2_match:
            direction = "ниже" if max_diff_signed < 0 else "выше"
            return (
                f"Максимальные потери в вашем банке обусловлены такими источниками риска, "
                f"как {top2_bank[0]} и {top2_bank[1]}: на них приходится {bank_pct_int}% потерь. "
                f"В банках-аналогах максимальные потери сконцентрированы в этих же категориях, "
                f"при этом их суммарная доля отличается от вашего банка - "
                f"{cluster_pct_int}% от всех потерь. "
                f"Максимальное различие отмечается в категории \"{max_diff_label}\": "
                f"в вашем банке доля соответствующих потерь на {max_diff_abs} п.п. "
                f"{direction} среднерыночной."
            )
        else:
            cluster_second = top2_cluster[1]
            return (
                f"Максимальные потери в вашем банке обусловлены такими источниками риска, "
                f"как {top2_bank[0]} и {top2_bank[1]}: на них приходится {bank_pct_int}% потерь. "
                f"В банках-аналогах максимальные потери также приходятся на источник "
                f"{top2_cluster[0]}, при этом на втором месте, в отличие от вашего банка, "
                f"- {cluster_second}, суммарно на эти два источника приходится "
                f"{cluster_pct_int}% потерь."
            )
