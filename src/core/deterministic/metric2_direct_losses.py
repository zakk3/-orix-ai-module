from typing import Dict, Any, List, Optional, Tuple
import statistics
import random

from src.models.output_models import MetricCalculations


# Минимум кварталов для расчёта тренда
MIN_QUARTERS_FOR_TREND = 3

# Окно для оценки тренда — 3 квартала, как пишут аналитики ОРИКС
TREND_WINDOW = 3

# Порог наклона для классификации тренда (отношение к среднему уровню).
# Подобраны под стиль аналитиков ОРИКС:
#   < 0.5% — стабильный
#   0.5% – 2% — незначительный (рост/снижение)
#   > 2% — выраженный (рост/снижение)
SLOPE_STABLE_THRESHOLD = 0.005
SLOPE_SLIGHT_THRESHOLD = 0.02

# Пороги для классификации расхождения трендов
RATIO_VOLATILE_THRESHOLD = 5.0     # отношение max/median > 5 — высокая волатильность

# Классификация уровня убытков относительно рынка (median self / median rest)
LOSS_LEVEL_LOW_THRESHOLD = 0.5     # < 0.5 — невысокий
LOSS_LEVEL_HIGH_THRESHOLD = 2.0    # > 2.0 — высокий

# Порог в млн руб. для критерия "крупных" квартальных потерь
HIGH_LOSS_THRESHOLD_MLN = 2.5

# Пороги для классификации волатильности (max self / median self)
VOLATILITY_HIGH_THRESHOLD = 50      # > 50 — высокая
VOLATILITY_MODERATE_THRESHOLD = 5   # > 5 — значительная


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

        # Тренды за последние TREND_WINDOW кварталов с защитой от выбросов
        bank_trend = self._classify_trend(self_values[-TREND_WINDOW:], all_values=self_values)
        market_trend = self._classify_trend(rest_values[-TREND_WINDOW:], all_values=rest_values)

        # Готовая формулировка тренда банка для предложения 2 сценария «существенно отличаются».
        # Сильный тренд («рост»/«снижение») → добавляем «планомерный/-ое» и «потерь».
        # Слабый тренд → добавляем только «потерь».
        _trend_display_map = {
            "рост":                    "планомерный рост потерь",
            "снижение":                "планомерное снижение потерь",
            "незначительный рост":     "незначительный рост потерь",
            "незначительное снижение": "незначительное снижение потерь",
            "стабильный":              "стабильный уровень потерь",
        }
        bank_trend_display = _trend_display_map.get(bank_trend, bank_trend)
        market_trend_display = _trend_display_map.get(market_trend, market_trend)

        # Расхождение трендов и общая характеристика
        divergence_label = self._divergence_label(
            self_values, rest_values, bank_trend, market_trend
        )

        # Стабильное превышение / занижение на всём периоде
        consistent_above = all(s > r for s, r in zip(self_values, rest_values))
        consistent_below = all(s < r for s, r in zip(self_values, rest_values))

        # Мажоритарное правило: банк ниже/выше рынка в большинстве периодов.
        # Используется для сценариев с одним-двумя аномальными кварталами
        # (например «драматично отличаются»), где consistent_* = false,
        # но общая картина всё равно ясна.
        below_count = sum(1 for s, r in zip(self_values, rest_values) if s < r)
        above_count = len(self_values) - below_count
        mostly_below = below_count > len(self_values) / 2
        mostly_above = above_count > len(self_values) / 2

        # Готовое предложение про размерные классы (если применимо)
        if consistent_above:
            size_class_sentence = (
                "Постоянное стабильное превышение ваших потерь над усреднёнными "
                "потерями банков сравнения может также говорить о различиях "
                "в размерных классах вашего банка и объектов сравнения."
            )
        elif consistent_below:
            size_class_sentence = (
                "Постоянное стабильное превышение усреднённых потерь над потерями "
                "вашего банка может также говорить о различиях в размерных классах "
                "вашего банка и объектов сравнения."
            )
        else:
            size_class_sentence = ""

        # Для сценария «драматично» — словесное описание превалирующего положения
        if mostly_below:
            mostly_position_label = "ниже"
        elif mostly_above:
            mostly_position_label = "выше"
        else:
            mostly_position_label = "сопоставимо со"

        # Проверяем волатильность (для сценариев типа «драматично отличаются»)
        volatile = self._is_volatile(self_values)

        # Форматируем последний квартал в человеческий вид: "2025Q3" → "Q3 2025"
        last_q_label_human = self._format_quarter(labels[-1])

        # Магнитуда отношения для текста («больше» или «меньше», во сколько раз)
        last_q_direction = "больше" if last_q_ratio > 1 else "меньше"
        last_4q_direction = "больше" if last_4q_ratio > 1 else "меньше"
        last_q_factor = last_q_ratio if last_q_ratio > 1 else 1.0 / last_q_ratio
        last_4q_factor = last_4q_ratio if last_4q_ratio > 1 else 1.0 / last_4q_ratio

        # ── Дополнительные поля для сценария «драматично отличаются» ──

        # Уровень убытков банка относительно рынка (по медиане)
        loss_level, loss_level_label = self._classify_loss_level(self_values, rest_values)

        # Динамический порог "аномальных" потерь — 5× медианы по всем периодам.
        median_self = statistics.median(self_values)
        anomaly_threshold = max(5.0 * median_self, 1.0)
        last_4_self = self_values[-4:]
        high_loss_count = sum(1 for v in last_4_self if v > anomaly_threshold)

        # Пиковый квартал — где self/rest было максимальным
        peak_quarter_label, peak_factor, peak_direction = self._find_peak_quarter(
            self_values, rest_values, labels
        )

        # Уровень волатильности
        volatility_level = self._classify_volatility(self_values)

        # Готовое предложение о пике (грамматически корректное, вставляется дословно)
        if peak_direction == "превысили":
            peak_sentence = (
                f"в {peak_quarter_label} потери вашего банка более чем в "
                f"{self._fmt_factor(peak_factor)} раза превысили потери банков сравнения"
            )
        else:
            peak_sentence = (
                f"в {peak_quarter_label} потери вашего банка более чем в "
                f"{self._fmt_factor(peak_factor)} раза оказались ниже средних потерь "
                f"банков сравнения"
            )

        # Готовое предложение-интерпретация для сценария «драматично» (вставляется дословно)
        if mostly_below:
            drama_interpretation_sentence = (
                "Несмотря на то что почти во всех периодах величина потерь вашего банка "
                "в несколько раз меньше средних потерь банков сравнения, данная ситуация "
                "требует внимания, т.к. разовые крупные потери вашего банка, кратно "
                "превышающие среднерыночные, свидетельствуют о наличии в банке рисков "
                "высокого уровня, не до конца минимизированных системой контрольных процедур."
            )
        elif mostly_above:
            drama_interpretation_sentence = (
                "Несмотря на то что в большинстве периодов величина потерь вашего банка "
                "выше средних потерь банков сравнения, разовые крупные отклонения "
                "свидетельствуют о наличии в банке рисков высокого уровня, не до конца "
                "минимизированных системой контрольных процедур."
            )
        else:
            drama_interpretation_sentence = (
                "Несмотря на то что в большинстве периодов величина потерь вашего банка "
                "сопоставима со средними потерями банков сравнения, разовые крупные "
                "отклонения свидетельствуют о наличии в банке рисков высокого уровня, "
                "не до конца минимизированных системой контрольных процедур."
            )

        _count_words = {0: "ни одном", 1: "одном", 2: "двух", 3: "трёх", 4: "четырёх"}
        high_loss_count_word = _count_words.get(high_loss_count, str(high_loss_count))

        # Готовые предложения о причинах (предложение 3) — по сценарию расхождения.
        # «Драматично» не имеет предложения о причинах — там drama_interpretation_sentence.
        #
        # ВАЖНО: у каждого сценария НЕСКОЛЬКО вариантов формулировки, и выбор
        # случайный при каждом вызове. Если бы вариант был один (константа),
        # то для ЛЮБОГО банка этой категории текст совпадал бы и с эталоном
        # golden set (построенным на той же константе), и с самим собой при
        # повторных запросах — LLM просто копировал бы готовый текст вместо
        # перефразирования, потому что не было ничего отличного для замены.
        _reason_sentence_variants = {
            "в целом совпадают": [
                "Такая схожая динамика, возможно, обусловлена влиянием одинаковых источников риска.",
                "Подобное сходство трендов, вероятно, связано с воздействием общих факторов риска.",
                "Такое совпадение динамики, не исключено, объясняется влиянием схожих источников риска.",
            ],
            "незначительно отличаются": [
                "Незначительность различий, возможно, обусловлена влиянием одинаковых источников риска.",
                "Слабая выраженность расхождений, вероятно, связана с воздействием общих факторов риска.",
                "Подобная близость показателей, не исключено, объясняется влиянием схожих источников риска.",
            ],
            "несколько отличаются": [
                "Такая динамика в вашем банке, возможно, обусловлена особенностями учёта "
                "отдельных операций или различиями в составе продуктов.",
                "Подобная тенденция в вашем банке, вероятно, связана с особенностями учёта "
                "отдельных операций или отличиями в составе продуктов.",
                "Данное отклонение в вашем банке, не исключено, объясняется спецификой учёта "
                "отдельных операций или различиями в линейке продуктов.",
            ],
            "существенно отличаются": [
                "Такое расхождение, возможно, обусловлено особенностями учёта потерь "
                "или спецификой бизнес-модели банка.",
                "Подобное различие, вероятно, связано с особенностями учёта потерь "
                "или спецификой бизнес-модели банка.",
                "Данное отклонение, не исключено, объясняется особенностями учёта потерь "
                "или спецификой бизнес-модели банка.",
            ],
        }
        _reason_variants = _reason_sentence_variants.get(divergence_label, [])
        reason_sentence = random.choice(_reason_variants) if _reason_variants else ""

        # Рекомендация (предложение 4) — несколько вариантов, выбор случайный
        _recommendation_variants = [
            "Рекомендуем дополнительно проанализировать структуру источников потерь "
            "вашего банка и других банков.",
            "Советуем детально изучить структуру источников потерь "
            "вашего банка и других банков.",
            "Целесообразно дополнительно проанализировать структуру источников потерь вашего банка по сравнению с другими банками.",
        ]
        recommendation_sentence = random.choice(_recommendation_variants)

        extra: Dict[str, Any] = {
            "last_quarter_label": last_q_label_human,
            "last_quarter_serie": labels[-1],
            "first_quarter_serie": labels[0],
            "total_quarters": len(self_values),

            "bank_trend_3q": bank_trend,
            "bank_trend_display": bank_trend_display,       # "планомерный рост потерь" / "незначительный рост потерь" etc.
            "market_trend_3q": market_trend,
            "market_trend_display": market_trend_display,
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
            "mostly_below_market": mostly_below,
            "mostly_above_market": mostly_above,
            "mostly_position_label": mostly_position_label,
            "size_class_sentence": size_class_sentence,
            "is_volatile": volatile,

            # Поля для сценария «драматично отличаются»
            "loss_level": loss_level,                       # "невысоким" / "средним" / "высоким"
            "loss_level_label": loss_level_label,           # "невысокий" / "средний" / "высокий"
            "high_loss_threshold_mln": HIGH_LOSS_THRESHOLD_MLN,
            "high_loss_count_last_4": high_loss_count,
            "high_loss_count_word": high_loss_count_word,   # "одном" / "двух" / "трёх" / "четырёх"
            "peak_quarter_label": peak_quarter_label,       # "Q2 2025"
            "peak_factor_fmt": self._fmt_factor(peak_factor),
            "peak_direction": peak_direction,               # "превысили" / "оказались ниже"
            "volatility_level": volatility_level,           # "высокой" / "значительной" / "умеренной"
            "peak_sentence": peak_sentence,                 # готовое предложение о пике
            "drama_interpretation_sentence": drama_interpretation_sentence,  # готовая интерпретация

            # Готовые предложения для синонимной замены (предложения 3 и 4)
            "reason_sentence": reason_sentence,
            "recommendation_sentence": recommendation_sentence,

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

    # ── Извлечение временного ряда ────────────────────────────────────────

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

    # ── Тренды ─────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_trend(values: List[float], all_values: List[float] = None) -> str:
        # Классификация тренда по изменению "первое значение vs последнее" в окне.
        # Если передан all_values — исключаем из окна выбросы (> 5× медианы полного ряда),
        # чтобы один аномальный квартал не искажал классификацию тренда.
        if len(values) < 2:
            return "стабильный"

        # Outlier exclusion: убираем значения, превышающие 5× медиану полного ряда
        if all_values and len(all_values) >= 3:
            series_median = statistics.median(all_values)
            if series_median > 0:
                outlier_threshold = 5.0 * series_median
                clean = [v for v in values if v <= outlier_threshold]
                if len(clean) >= 2:
                    values = clean

        first, last = values[0], values[-1]
        if first == 0:
            return "стабильный"

        change_pct = (last - first) / first * 100

        if abs(change_pct) < 2:
            return "стабильный"
        elif abs(change_pct) < 15:
            return "незначительный рост" if change_pct > 0 else "незначительное снижение"
        else:
            return "рост" if change_pct > 0 else "снижение"

    @staticmethod
    def _divergence_label(
        self_vals: List[float],
        rest_vals: List[float],
        bank_trend: str,
        market_trend: str,
    ) -> str:
        # Классификация расхождения трендов по 5-уровневой шкале

        # 1) Сначала проверяем волатильность отношений self/rest — это «драматично»
        ratios = [s / r for s, r in zip(self_vals, rest_vals) if r != 0]
        if ratios:
            max_r, min_r = max(ratios), min(ratios)
            spread = max_r / min_r if min_r > 0 else float('inf')
            if spread > 50:
                return "драматично отличаются"

        # Определяем направление и силу каждого тренда
        def parse(trend: str) -> Tuple[str, str]:
            # Возвращает (direction, strength): direction ∈ {рост, снижение, стабильный}
            # strength ∈ {strong, slight, stable}
            if "стабильный" in trend:
                return "стабильный", "stable"
            if "незначительн" in trend:
                direction = "рост" if "рост" in trend else "снижение"
                return direction, "slight"
            direction = "рост" if "рост" in trend else "снижение"
            return direction, "strong"

        bank_dir, bank_str = parse(bank_trend)
        market_dir, market_str = parse(market_trend)

        # 2) Оба тренда «стабильные» → совпадают
        if bank_str == "stable" and market_str == "stable":
            return "в целом совпадают"

        # 3) Один стабильный, другой нет
        if bank_str == "stable" or market_str == "stable":
            other_strength = market_str if bank_str == "stable" else bank_str
            if other_strength == "slight":
                return "незначительно отличаются"
            return "существенно отличаются"

        # Оба ненулевые — сравниваем направления
        same_direction = bank_dir == market_dir

        # 4) Одно направление, разная сила (рост+рост слабый, снижение+снижение слабое и т.д.)
        if same_direction:
            if bank_str == market_str:
                # Оба «незначительные» — сравниваем фактические темпы изменения.
                # Если темпы различаются более чем на 20% относительно большего — «незначительно отличаются».
                if bank_str == "slight":
                    b_first = self_vals[-3] if len(self_vals) >= 3 else self_vals[0]
                    m_first = rest_vals[-3] if len(rest_vals) >= 3 else rest_vals[0]
                    b_rate = abs((self_vals[-1] - b_first) / b_first) if b_first != 0 else 0.0
                    m_rate = abs((rest_vals[-1] - m_first) / m_first) if m_first != 0 else 0.0
                    max_rate = max(b_rate, m_rate)
                    if max_rate > 0 and abs(b_rate - m_rate) / max_rate > 0.20:
                        return "незначительно отличаются"
                return "в целом совпадают"
            return "существенно отличаются"

        # 5) Противоположные направления
        # Оба слабые (один слабый рост, другой слабое снижение) → несколько
        if bank_str == "slight" and market_str == "slight":
            return "несколько отличаются"
        # Один сильный, другой слабый — это уже сильное расхождение
        if (bank_str == "strong" and market_str == "slight") or \
           (bank_str == "slight" and market_str == "strong"):
            return "существенно отличаются"
        # Оба сильные противоположные → существенно
        return "существенно отличаются"

    # ── Соотношения и волатильность ───────────────────────────────────────

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

    @staticmethod
    def _classify_loss_level(
        self_vals: List[float], rest_vals: List[float]
    ) -> Tuple[str, str]:
        # Уровень убытков банка относительно рынка по медианам.
        # Возвращает (instrumental, nominative): "невысоким", "невысокий"
        self_med = statistics.median(self_vals)
        rest_med = statistics.median(rest_vals)
        if rest_med == 0:
            return "средним", "средний"
        ratio = self_med / rest_med
        if ratio < LOSS_LEVEL_LOW_THRESHOLD:
            return "невысоким", "невысокий"
        if ratio > LOSS_LEVEL_HIGH_THRESHOLD:
            return "высоким", "высокий"
        return "средним", "средний"

    @staticmethod
    def _classify_volatility(values: List[float]) -> str:
        # Уровень волатильности по отношению max/median (instrumental case)
        if len(values) < 4:
            return "умеренной"
        med = statistics.median(values)
        if med == 0:
            return "умеренной"
        ratio = max(values) / med
        if ratio > VOLATILITY_HIGH_THRESHOLD:
            return "высокой"
        if ratio > VOLATILITY_MODERATE_THRESHOLD:
            return "значительной"
        return "умеренной"

    @staticmethod
    def _find_peak_quarter(
        self_vals: List[float],
        rest_vals: List[float],
        labels: List[str],
    ) -> Tuple[str, float, str]:
        # Находим квартал с максимальным отношением self/rest.
        # Возвращает (quarter_label, factor, direction)
        # direction: "превысили" если банк выше рынка, "оказались ниже" — если меньше
        ratios = [
            (s / r if r > 0 else 0.0, label, s, r)
            for s, r, label in zip(self_vals, rest_vals, labels)
        ]
        peak_ratio, peak_serie, peak_self, peak_rest = max(ratios, key=lambda x: x[0])

        if peak_ratio > 1:
            factor = peak_ratio
            direction = "превысили"
        else:
            factor = 1.0 / peak_ratio if peak_ratio > 0 else 0.0
            direction = "оказались ниже"

        # Форматируем квартал: "2025Q2" → "Q2 2025"
        if "Q" in peak_serie:
            parts = peak_serie.split("Q")
            if len(parts) == 2 and parts[0].isdigit():
                peak_serie = f"Q{parts[1]} {parts[0]}"

        return peak_serie, factor, direction

    # ── Форматирование ─────────────────────────────────────────────────────

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
        # Коэффициент в русском формате: 1.4 → "1,4"
        return f"{val:.1f}".replace(".", ",")
