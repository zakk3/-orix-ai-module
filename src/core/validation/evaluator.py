"""
evaluator.py — оценка качества аналитического вывода LLM.

Проверяет два класса проблем:
1. Универсальные (для всех метрик): длина текста, английские слова,
   запрещённые формулировки-предположения, числа-галлюцинации.
2. Специфичные для метрики: упомянуты ли в тексте конкретные факты
   (позиция, медиана, тренд и т.д.), которые калькулятор подготовил
   для LLM — то есть проверка, что LLM не потерял важные данные при
   перефразировании готовых предложений.

score = max(0.0, 1.0 - 0.15 * число_ошибок)
"""

import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import Dict

from src.models.output_models import MetricCalculations


# ═══════════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════════

# Числа разрешённые всегда: стандартные, отраслевые пороги, репрезентативность
ALWAYS_ALLOWED = {
    "0", "1", "2", "3", "4", "5",
    "10", "50", "100",
    "0.5", "0,5", "0.8", "0,8", "0.96", "0,96",
    "62", "62.0", "62,0",
}

# Паттерны для очистки текста от безопасных конструкций перед поиском
# чисел-галлюцинаций (даты, кварталы, "в N раз", фиксированные проценты)
DATE_PATTERNS = [
    r'\b20[2-3]\d\b',
    r'\b[1-4]\s*-?[оыйемя]*\s*кв[а-яё.-]*',
    r'\bQ[1-4]\b',
    r'\b[2-3]\d\s*г[а-яех.]*',
    r'\bв\s+\d+(?:[.,]\d+)?\s+раз[а]?\b',
    r'\bна\s+100\s*%\b',
    r'\bна\s+50\s*%\b',
    r'\b62\s*%\b',
]

# Запрещённые формулировки-предположения без опоры на данные — полный
# список, реально запрещённый в prompt_builder.py (DOMAIN_INSTRUCTIONS),
# а не только две фразы, как было раньше.
FORBIDDEN_PHRASES = [
    "скорее всего",
    "не исключено",
    "может свидетельствовать",
    "может указывать",
    "более эффективном управлении",
    "свидетельствует об эффективности",
    "что говорит о",
]
FORBIDDEN_WORDS_PATTERN = re.compile(
    "|".join(re.escape(p) for p in FORBIDDEN_PHRASES), re.IGNORECASE
)

# Латинские буквы в тексте (запрет английского кроме обозначений кварталов)
ENGLISH_PATTERN = re.compile(r'[A-Za-z]+')
ENGLISH_WHITELIST = re.compile(r'\bQ[1-4]\b')

# Слова, свидетельствующие об экстремальном значении (для Метрики 1)
EXTREME_WORDS_PATTERN = re.compile(
    r'наихудш|экстремальн|аномальн|значительн|существенн|'
    r'наибольш|максимальн|критическ|крайне\s+высок|'
    r'самом?\s+высок|самом?\s+низк|наивысш',
    re.IGNORECASE
)

# Числительные прописью — LLM иногда пишет "пятое место", "десяти банков"
# вместо цифр при перефразировании готового предложения. Порядковые (для
# позиции, "X-е место") и количественные родительного падежа (для общего
# числа банков, "из X банков") у некоторых чисел различаются корнем
# (1, 2, 4, 7), поэтому используются два отдельных словаря.
ORDINAL_STEMS = {
    1: "перв", 2: "втор", 3: "трет", 4: "четверт", 5: "пят",
    6: "шест", 7: "седьм", 8: "восьм", 9: "девят", 10: "десят",
    11: "одиннадцат", 12: "двенадцат", 13: "тринадцат", 14: "четырнадцат",
    15: "пятнадцат", 16: "шестнадцат", 17: "семнадцат", 18: "восемнадцат",
    19: "девятнадцат", 20: "двадцат",
}
CARDINAL_STEMS = {
    1: "одн", 2: "дву", 3: "тре", 4: "четыре", 5: "пят",
    6: "шест", 7: "сем", 8: "восьм", 9: "девят", 10: "десят",
    11: "одиннадцат", 12: "двенадцат", 13: "тринадцат", 14: "четырнадцат",
    15: "пятнадцат", 16: "шестнадцат", 17: "семнадцат", 18: "восемнадцат",
    19: "девятнадцат", 20: "двадцат",
}


# ═══════════════════════════════════════════════════════════════════════════
# Общие вспомогательные функции
# ═══════════════════════════════════════════════════════════════════════════

def _stem_match(text: str, label: str, min_word_len: int = 5, stem_len: int = 6) -> bool:
    """
    True, если в тексте встретился хотя бы один характерный корень из label.
    Используется там, где LLM перефразирует готовую метку, но хотя бы одно
    ключевое слово должно сохраниться (намеренно мягкая проверка — LLM
    разрешено заменять синонимами, в т.ч. терять второстепенные уточнения
    типа «несколько»/«существенно», если основной смысл сохранён).
    """
    if not label:
        return True  # нет метки — нечего проверять, пропускаем

    # Берём только "длинные" слова (короткие типа "выше"/"ниже" не годятся
    # в качестве уникального корня — слишком общие)
    stems = [w[:stem_len] for w in label.split() if len(w) >= min_word_len]
    if not stems:
        return True

    text_lower = text.lower()
    return any(s in text_lower for s in stems)  # совпадения хотя бы одного корня достаточно


def _number_mentioned(verdict: str, n: int, stems: Dict[int, str]) -> bool:
    """Число упомянуто цифрой ИЛИ словом (с учётом корня и ё/е)."""
    if str(n) in verdict:
        return True
    stem = stems.get(n)
    if not stem:
        return False
    text = verdict.lower().replace('ё', 'е')
    return stem.replace('ё', 'е') in text


def _value_mentioned(verdict: str, value_fmt) -> bool:
    """Числовое значение упомянуто хотя бы в одной форме (точка/запятая)."""
    if value_fmt is None or value_fmt == "":
        return True
    s = str(value_fmt)
    dot = s.replace(",", ".")
    comma = s.replace(".", ",")
    return dot in verdict or comma in verdict


def _number_variants(val: float) -> set:
    """Все допустимые варианты записи числа (округления, запятая вместо точки)."""
    variants = set()
    abs_val = abs(val)

    # Перебираем 0-3 знака после запятой — LLM может округлить число
    # сильнее, чем в исходных расчётах (67.32 -> "67,3" или "67")
    for nd in range(4):
        rounded = round(abs_val, nd)
        s = f"{rounded:.{nd}f}"
        stripped = s.rstrip('0').rstrip('.') if '.' in s else s  # "67.30" -> "67.3"
        for variant in [s, stripped]:
            variants.add(variant)
            variants.add(variant.replace('.', ','))  # русская десятичная запятая

        # Decimal с двумя режимами округления — Python round() может дать
        # другой результат, чем "банковское" округление половины
        try:
            d = Decimal(str(abs_val))
            q = Decimal('1.' + '0' * nd) if nd > 0 else Decimal('1')
            for rounding in [ROUND_HALF_UP, ROUND_HALF_EVEN]:
                r = str(d.quantize(q, rounding=rounding))
                if r.endswith('.0'):
                    r_stripped = r[:-2]
                elif '.' in r:
                    r_stripped = r.rstrip('0').rstrip('.')
                else:
                    r_stripped = r
                for variant in [r, r_stripped]:
                    variants.add(variant)
                    variants.add(variant.replace('.', ','))
        except Exception:
            pass  # Decimal не справился — варианты округления просто не добавляются

    # Отрицательные числа: добавляем варианты и для модуля (на случай,
    # если в тексте число упомянуто без знака минус)
    if val < 0:
        variants.update(_number_variants(abs_val))
    return variants


# ═══════════════════════════════════════════════════════════════════════════
# Универсальные проверки (применяются ко всем метрикам)
# ═══════════════════════════════════════════════════════════════════════════

def check_min_length(verdict: str, calc: MetricCalculations) -> list:
    """Слишком короткий вывод недостаточно информативен."""
    if len(verdict) < 100:
        return [f"Вывод слишком короткий ({len(verdict)} симв., минимум 100)"]
    return []


def check_english_words(verdict: str, calc: MetricCalculations) -> list:
    """В тексте не должно быть латиницы кроме обозначений кварталов (Q1-Q4)."""
    cleaned = ENGLISH_WHITELIST.sub('', verdict)
    matches = ENGLISH_PATTERN.findall(cleaned)
    if matches:
        unique = list(set(matches))[:5]
        return [f"Найдены английские слова: {', '.join(unique)}"]
    return []


def check_forbidden_words(verdict: str, calc: MetricCalculations) -> list:
    """Запрещены конструкции предположений без опоры на данные (см. FORBIDDEN_PHRASES)."""
    matches = FORBIDDEN_WORDS_PATTERN.findall(verdict)
    if matches:
        return [f"Запрещённое выражение: '{matches[0]}'"]
    return []


def check_hallucinated_numbers(verdict: str, calc: MetricCalculations) -> list:
    """Все числа в тексте должны быть из расчётов или из белого списка."""
    # Шаг 1: убираем из текста "безопасные" числа (даты, кварталы, "в N раз"),
    # чтобы они не попали в список чисел для проверки
    cleaned = verdict
    for pattern in DATE_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?<=\d)\s+(?=\d)', '', cleaned)  # склеиваем разорванные пробелом числа

    # Шаг 2: извлекаем все оставшиеся числа из текста
    raw_numbers = re.findall(r'[-+–−]?\d+[.,]?\d*', cleaned)

    # Шаг 3: нормализуем формат (убираем знак, запятая -> точка, лишние нули)
    numbers_in_text = []
    for n in raw_numbers:
        n = n.replace('–', '-').replace('−', '-').lstrip('+-')
        normalized = n.replace(',', '.')
        try:
            float(normalized)
            if '.' in normalized:
                normalized = normalized.rstrip('0').rstrip('.')
            numbers_in_text.append(normalized)
        except ValueError:
            pass  # не похоже на число — пропускаем

    # Шаг 4: собираем множество "разрешённых" чисел — белый список плюс
    # все числовые поля из MetricCalculations (включая extra)
    safe = set(ALWAYS_ALLOWED)
    for field, v in vars(calc).items():
        if isinstance(v, (int, float)):
            safe.update(_number_variants(v))
    for k, v in calc.extra.items():
        if isinstance(v, (int, float)):
            safe.update(_number_variants(v))
        if isinstance(v, str):
            # Числа внутри готовых предложений (extra со строковым значением)
            # тоже разрешены — например, число внутри outlier_sentence
            for n in re.findall(r'\d+[.,]?\d*', v):
                safe.add(n.replace(',', '.'))

    # Шаг 5: любое число из текста, не попавшее в safe — потенциальная галлюцинация
    errors = []
    for n in numbers_in_text:
        if n not in safe:
            errors.append(f"Возможная галлюцинация: число '{n}' не найдено в расчётах")
    return errors


# ═══════════════════════════════════════════════════════════════════════════
# Метрика 1 — Чистые потери к бизнес-индикатору (loss_share)
# ═══════════════════════════════════════════════════════════════════════════

def check_direction_loss_share(verdict: str, calc: MetricCalculations) -> list:
    """Направление выше/ниже не должно противоречить данным (медиана исключена из контекста)."""
    text = verdict.lower()
    text = re.sub(r'\bвыше\s+медианн\w*', '', text)
    text = re.sub(r'\bниже\s+медианн\w*', '', text)
    if calc.is_below_average:
        if re.search(r'\bвыше\b', text) and not re.search(r'\bниже\b', text):
            return ["Противоречие направления: банк ниже среднего, вывод утверждает 'выше'"]
    else:
        if re.search(r'\bниже\b', text) and not re.search(r'\bвыше\b', text):
            return ["Противоречие направления: банк выше среднего, вывод утверждает 'ниже'"]
    return []


def check_position_mentioned(verdict: str, calc: MetricCalculations) -> list:
    """Позиция в рейтинге должна быть упомянута — цифрой или словом."""
    if calc.position and calc.total_banks:
        pos_ok = _number_mentioned(verdict, calc.position, ORDINAL_STEMS)
        total_ok = _number_mentioned(verdict, calc.total_banks, CARDINAL_STEMS)
        if not pos_ok or not total_ok:
            return [f"Позиция {calc.position} из {calc.total_banks} не упомянута"]
    return []


def check_magnitude_label_used(verdict: str, calc: MetricCalculations) -> list:
    """Характеристика отклонения (magnitude_label), вшитая в opening_sentence, должна отражаться в тексте."""
    label = calc.extra.get("magnitude_label", "")
    if not _stem_match(verdict, label):
        return [f"Характеристика отклонения '{label}' не отражена в тексте"]
    return []


def check_median_mentioned_m1(verdict: str, calc: MetricCalculations) -> list:
    """Медианное значение должно быть упомянуто в тексте."""
    median_fmt = calc.extra.get("median_value_fmt", "")
    if not _value_mentioned(verdict, median_fmt):
        return [f"Медианное значение '{median_fmt}' не упомянуто в тексте"]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Метрика 2 — Динамика прямых потерь (direct_losses_dynamics)
# ═══════════════════════════════════════════════════════════════════════════

def check_divergence_label_used(verdict: str, calc: MetricCalculations) -> list:
    """
    Характеристика расхождения должна быть в открывающем предложении.
    Сравнение по корню слова, так как в эталонах встречаются разные числа:
    «отличается»/«отличаются», «совпадает»/«совпадают».
    """
    label = calc.extra.get("divergence_label", "")
    if not label:
        return []

    stems = ["отлич", "совпад", "незначительн", "несколько", "драматичн", "существенн"]
    label_lower = label.lower()
    verdict_lower = verdict.lower()

    label_stems = [s for s in stems if s in label_lower]
    if label_stems and any(s in verdict_lower for s in label_stems):
        return []
    return [f"Характеристика расхождения '{label}' не использована"]


def check_last_quarter_mentioned(verdict: str, calc: MetricCalculations) -> list:
    """Последний квартал должен быть назван дословно (формат «Q3 2025»)."""
    label = calc.extra.get("last_quarter_label", "")
    if label and label not in verdict:
        return [f"Последний квартал '{label}' не упомянут"]
    return []


def check_ratios_present(verdict: str, calc: MetricCalculations) -> list:
    """В тексте должны быть оба коэффициента: за 4 квартала и за последний квартал."""
    errors = []
    last_4q = calc.extra.get("last_4q_factor_fmt", "")
    last_q = calc.extra.get("last_q_factor_fmt", "")
    if last_4q and last_4q not in verdict:
        errors.append(f"Коэффициент за 4 квартала '{last_4q}' не упомянут")
    if last_q and last_q not in verdict:
        errors.append(f"Коэффициент за последний квартал '{last_q}' не упомянут")
    return errors


def check_trend_direction(verdict: str, calc: MetricCalculations) -> list:
    """Направление тренда банка не должно противоречить данным."""
    bank_trend = calc.extra.get("bank_trend_3q", "")
    text = verdict.lower()

    # Данные говорят "рост" -> в тексте не должно быть слов о снижении
    if "рост" in bank_trend and re.search(r'(?:снижени[ея]|сниж[аи]|пад[аеи]|спад)', text):
        return [f"Противоречие тренда: данные '{bank_trend}', текст говорит о снижении"]

    # Данные говорят "снижение" -> проверяем именно рост БАНКА (не рынка),
    # т.к. фраза «рынок растёт» в тексте — это нормально и не противоречие
    if "снижение" in bank_trend and re.search(r'(?:рост|увеличени[ея]|растёт|растет)', text):
        if re.search(r'ваш[а-я]*\s+банк[а-я]*.{0,40}(?:рост|увеличени|растёт|растет)', text):
            return [f"Противоречие тренда: данные '{bank_trend}', текст говорит о росте банка"]
    return []


def check_size_class_mentioned_m2(verdict: str, calc: MetricCalculations) -> list:
    """Если банк стабильно выше/ниже рынка — предложение о размерных классах обязательно."""
    sentence = calc.extra.get("size_class_sentence", "")
    if not sentence:
        return []
    if "размерн" not in verdict.lower():
        return ["Предложение о размерных классах отсутствует в тексте (consistent_above или consistent_below истинно)"]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Метрика 3 — Распределение по бакетам потерь (loss_buckets)
# ═══════════════════════════════════════════════════════════════════════════

# Метка сценария (Метрика 3) -> корни слов, любой из которых должен
# встретиться в тексте, чтобы сценарий считался отражённым
_M3_SCENARIO_STEMS = {
    "незначительные отклонения": ["незначительн"],
    "расхождения": ["расхожден"],
    "кардинально отличается": ["кардинальн"],
}


def check_scenario_label_used_m3(verdict: str, calc: MetricCalculations) -> list:
    """Метка сценария должна присутствовать в тексте вывода."""
    scenario = calc.extra.get("scenario_label", "")
    keywords = _M3_SCENARIO_STEMS.get(scenario)
    if keywords and not any(k in verdict.lower() for k in keywords):
        return [f"Сценарий '{scenario}' не отражён в тексте"]
    return []


def check_total_deviation_mentioned_m3(verdict: str, calc: MetricCalculations) -> list:
    """Суммарное отклонение (п.п.) должно быть упомянуто."""
    total = calc.extra.get("total_deviation")
    if total is None:
        return []
    if not _value_mentioned(verdict, total):
        return [f"Суммарное отклонение '{total} п.п.' не упомянуто в тексте"]
    return []


def check_max_diff_bucket_mentioned_m3(verdict: str, calc: MetricCalculations) -> list:
    """Бакет с максимальным отклонением должен быть упомянут (для расхождений)."""
    scenario = calc.extra.get("scenario_label", "")
    if scenario not in ("расхождения", "кардинально отличается"):
        return []
    bucket = calc.extra.get("max_diff_bucket", "")
    # Очищенная метка (без "+") — LLM пишет «от 7000 тыс.руб.», а не «7000+»
    bucket_clean = bucket.rstrip("+") if bucket else ""
    if bucket_clean and bucket_clean not in verdict:
        return [f"Бакет с максимальным отклонением '{bucket_clean}' не упомянут"]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Метрика 4 — Уровень возмещения прямых потерь (recovery_level)
# ═══════════════════════════════════════════════════════════════════════════

# Метка сценария (Метрика 4) -> корни слов для проверки
_M4_SCENARIO_STEMS = {
    "соответствует":                  ["соответствует", "соответствуют"],
    "существенные отклонения":        ["существенн"],
    "весьма существенные отклонения": ["весьма существенн"],
    "выше среднего":                  ["выше"],
}


def check_scenario_label_used_m4(verdict: str, calc: MetricCalculations) -> list:
    """Метка сценария должна отражаться в тексте вывода."""
    scenario = calc.extra.get("scenario_label", "")
    keywords = _M4_SCENARIO_STEMS.get(scenario, [])
    if keywords and not any(k in verdict.lower() for k in keywords):
        return [f"Сценарий '{scenario}' не отражён в тексте вывода"]
    return []


def check_diff_abs_mentioned_m4(verdict: str, calc: MetricCalculations) -> list:
    """Для сценариев с отклонением значение п.п. должно быть упомянуто."""
    scenario = calc.extra.get("scenario_label", "")
    if scenario == "соответствует":
        return []  # конкретная цифра п.п. не обязательна
    diff_abs = calc.extra.get("diff_abs")
    if diff_abs is None:
        return []
    if not _value_mentioned(verdict, diff_abs):
        return [f"Отклонение '{diff_abs} п.п.' не упомянуто в тексте"]
    return []


def check_direction_m4(verdict: str, calc: MetricCalculations) -> list:
    """Направление (выше/ниже) не должно противоречить данным."""
    scenario = calc.extra.get("scenario_label", "")
    if scenario == "соответствует":
        return []  # направление не критично

    text = verdict.lower()
    is_above = calc.extra.get("is_above_average", False)

    if is_above:
        if re.search(r'\bниже\b', text) and not re.search(r'\bвыше\b', text):
            return ["Противоречие направления: банк выше среднего, вывод говорит 'ниже'"]
    else:
        if re.search(r'\bвыше\b', text) and not re.search(r'\bниже\b', text):
            return ["Противоречие направления: банк ниже среднего, вывод говорит 'выше'"]
    return []


def check_representativeness_mentioned_m4(verdict: str, calc: MetricCalculations) -> list:
    """Процент репрезентативности и упоминание ОРИКС должны быть в тексте (footer_sentence)."""
    errors = []
    pct = calc.extra.get("representativeness_pct", 62)
    pct_str = f"{pct}%"
    if pct_str not in verdict:
        errors.append(f"Репрезентативность '{pct_str}' не упомянута в тексте")
    if "ОРИКС" not in verdict:
        errors.append("Слово 'ОРИКС' отсутствует в тексте")
    return errors


# ═══════════════════════════════════════════════════════════════════════════
# Метрика 5 — Распределение по источникам риска (concentration)
# ═══════════════════════════════════════════════════════════════════════════

# Метка сценария (Метрика 5) -> корни слов для проверки
_M5_SCENARIO_STEMS = {
    "идентична":              ["идентичн"],
    "некоторые отличия":      ["некоторы", "отличи"],
    "некоторые различия":     ["некоторы", "различи", "отличи"],
    "умеренные различия":     ["умеренн", "отличает"],
    "значительно отличается": ["значительн"],
}


def check_scenario_label_used_m5(verdict: str, calc: MetricCalculations) -> list:
    """Ключевое слово сценария должно присутствовать в тексте."""
    scenario = calc.extra.get("scenario_label", "")
    keywords = _M5_SCENARIO_STEMS.get(scenario, [scenario[:6]] if scenario else [])
    if keywords and not any(kw in verdict.lower() for kw in keywords):
        return [f"Сценарий '{scenario}' не отражён в тексте"]
    return []


def check_n_significant_mentioned_m5(verdict: str, calc: MetricCalculations) -> list:
    """Количество источников с существенным отклонением должно быть упомянуто."""
    n = calc.extra.get("n_significant", 0)
    if n == 0:
        return []  # «ни по одному» — достаточно факта отсутствия отклонений
    if str(n) not in verdict:
        return [f"Количество источников с существенным отклонением '{n}' не упомянуто"]
    return []


def check_top2_bank_mentioned_m5(verdict: str, calc: MetricCalculations) -> list:
    """Оба топ-2 источника банка должны быть упомянуты в тексте."""
    top2 = calc.extra.get("top2_bank", [])
    errors = []
    text = verdict.lower()
    for source in top2:
        first_word = source.split()[0].lower()
        stem = first_word[:6]
        if stem not in text:
            errors.append(f"Топ-2 источник банка '{source}' не упомянут в тексте")
    return errors


def check_nedostatki_alert_m5(verdict: str, calc: MetricCalculations) -> list:
    """Если alert сработал — в тексте должно быть упоминание «Недостатки процессов»."""
    if not calc.extra.get("has_nedostatki_alert", False):
        return []
    if "недостатки процессов" not in verdict.lower():
        return ["Блок тревоги по 'Недостатки процессов' не включён в текст"]
    diff_abs = calc.extra.get("nedostatki_diff_abs")
    if diff_abs is not None and not _value_mentioned(verdict, diff_abs):
        return [f"Отклонение по Недостаткам процессов '{diff_abs} п.п.' не упомянуто"]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Evaluator
# ═══════════════════════════════════════════════════════════════════════════

class Evaluator:
    """Оценивает вывод LLM: универсальные проверки + специфичные для метрики."""

    # Применяются к выводу ЛЮБОЙ метрики
    UNIVERSAL_CHECKS = [
        check_min_length,
        check_english_words,
        check_forbidden_words,
        check_hallucinated_numbers,
    ]

    # Применяются только к выводу конкретной метрики (по calc.metric_type)
    METRIC_CHECKS = {
        "loss_share": [
            check_direction_loss_share,
            check_position_mentioned,
            check_magnitude_label_used,
            check_median_mentioned_m1,
        ],
        "direct_losses_dynamics": [
            check_divergence_label_used,
            check_last_quarter_mentioned,
            check_ratios_present,
            check_trend_direction,
            check_size_class_mentioned_m2,
        ],
        "loss_buckets": [
            check_scenario_label_used_m3,
            check_total_deviation_mentioned_m3,
            check_max_diff_bucket_mentioned_m3,
        ],
        "recovery_level": [
            check_scenario_label_used_m4,
            check_diff_abs_mentioned_m4,
            check_direction_m4,
            check_representativeness_mentioned_m4,
        ],
        "concentration": [
            check_scenario_label_used_m5,
            check_n_significant_mentioned_m5,
            check_top2_bank_mentioned_m5,
            check_nedostatki_alert_m5,
        ],
    }

    def evaluate(self, verdict: str, calc: MetricCalculations) -> tuple:
        """Возвращает (passed, score, errors)."""
        errors = []

        # Универсальные проверки — всегда
        for fn in self.UNIVERSAL_CHECKS:
            errors.extend(fn(verdict, calc))

        # Проверки конкретной метрики — берём по типу из calc.metric_type
        for fn in self.METRIC_CHECKS.get(calc.metric_type, []):
            errors.extend(fn(verdict, calc))

        passed = len(errors) == 0
        score = max(0.0, 1.0 - 0.15 * len(errors))  # каждая ошибка снимает 0.15 балла
        return passed, round(score, 2), errors
