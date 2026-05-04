import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN

from src.models.output_models import MetricCalculations


# Константы 

# Числа разрешённые всегда: стандартные, отраслевые пороги, репрезентативность
ALWAYS_ALLOWED = {
    "0", "1", "2", "3", "4", "5",
    "10", "50", "100",
    "0.5", "0,5", "0.8", "0,8", "0.96", "0,96",
    "62", "62.0", "62,0",
}

# Паттерны для очистки текста от безопасных конструкций
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

# Слова свидетельствующие об экстремальном значении (для Метрики 1)
EXTREME_WORDS_PATTERN = re.compile(
    r'наихудш|экстремальн|аномальн|значительн|существенн|'
    r'наибольш|максимальн|критическ|крайне\s+высок|'
    r'самом?\s+высок|самом?\s+низк|наивысш',
    re.IGNORECASE
)

# Запрещённые слова (предположения без данных) — общая проверка
FORBIDDEN_WORDS_PATTERN = re.compile(
    r'\b(?:скорее\s+всего|не\s+исключено)\b',
    re.IGNORECASE
)

# Латинские буквы в тексте (запрет английского) — общая проверка
ENGLISH_PATTERN = re.compile(r'[A-Za-z]+')

# Слова которые НЕ считаются английским (Q1, Q2 и т.п. — это кварталы)
ENGLISH_WHITELIST = re.compile(r'\bQ[1-4]\b')


# Универсальные проверки (применяются ко всем метрикам)

def check_min_length(verdict: str, calc: MetricCalculations) -> list:
    # Минимальная длина текста — слишком короткий вывод недостаточно информативен
    if len(verdict) < 100:
        return [f"Вывод слишком короткий ({len(verdict)} симв., минимум 100)"]
    return []


def check_english_words(verdict: str, calc: MetricCalculations) -> list:
    # В тексте не должно быть латиницы кроме разрешённых обозначений (Q1, Q2 и т.п.)
    cleaned = ENGLISH_WHITELIST.sub('', verdict)
    matches = ENGLISH_PATTERN.findall(cleaned)
    if matches:
        unique = list(set(matches))[:5]
        return [f"Найдены английские слова: {', '.join(unique)}"]
    return []


def check_forbidden_words(verdict: str, calc: MetricCalculations) -> list:
    # Запрещены конструкции предположений без данных
    matches = FORBIDDEN_WORDS_PATTERN.findall(verdict)
    if matches:
        return [f"Запрещённое выражение: '{matches[0]}'"]
    return []


def check_hallucinated_numbers(verdict: str, calc: MetricCalculations) -> list:
    # Все числа в тексте должны быть из расчётов или из белого списка
    cleaned = verdict
    for pattern in DATE_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?<=\d)\s+(?=\d)', '', cleaned)

    raw_numbers = re.findall(r'[-+–−]?\d+[.,]?\d*', cleaned)

    # Нормализация: убираем знак, переводим запятую в точку, обрезаем нули
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
            pass

    # Собираем разрешённые числа из всех полей расчётов
    safe = set(ALWAYS_ALLOWED)
    for field, v in vars(calc).items():
        if isinstance(v, (int, float)):
            safe.update(_number_variants(v))
    for k, v in calc.extra.items():
        if isinstance(v, (int, float)):
            safe.update(_number_variants(v))
        if isinstance(v, str):
            for n in re.findall(r'\d+[.,]?\d*', v):
                safe.add(n.replace(',', '.'))

    errors = []
    for n in numbers_in_text:
        if n not in safe:
            errors.append(f"Возможная галлюцинация: число '{n}' не найдено в расчётах")
    return errors


# Проверки для Метрики 1 (loss_share)

def check_direction_loss_share(verdict: str, calc: MetricCalculations) -> list:
    # Направление выше/ниже не должно противоречить данным
    text = verdict.lower()
    if calc.is_below_average:
        if re.search(r'\bвыше\b', text) and not re.search(r'\bниже\b', text):
            return ["Противоречие направления: банк ниже среднего, вывод утверждает 'выше'"]
    else:
        if re.search(r'\bниже\b', text) and not re.search(r'\bвыше\b', text):
            return ["Противоречие направления: банк выше среднего, вывод утверждает 'ниже'"]
    return []


def check_position_mentioned(verdict: str, calc: MetricCalculations) -> list:
    # Позиция в рейтинге должна быть упомянута
    if calc.position and calc.total_banks:
        if str(calc.position) not in verdict or str(calc.total_banks) not in verdict:
            return [f"Позиция {calc.position} из {calc.total_banks} не упомянута"]
    return []


def check_extreme_mention(verdict: str, calc: MetricCalculations) -> list:
    # При позиции в нижних 25% выборки нужен вывод об экстремальном значении
    pos = calc.position or 0
    total = calc.total_banks or 1
    ratio = pos / total if total > 0 else 0
    if ratio >= 0.75 and not EXTREME_WORDS_PATTERN.search(verdict):
        return [f"Пропущен вывод об экстремальном значении при позиции {pos}/{total}"]
    return []


def check_exaggeration(verdict: str, calc: MetricCalculations) -> list:
    # «Существенно» и «значительно» допустимы только при отклонении ≥ 50%
    diff = calc.difference_percent
    if diff < 50:
        match = re.search(
            r'(существенно|значительно)\s+(ниже|выше|отлич)',
            verdict, re.IGNORECASE
        )
        if match:
            return [f"Преувеличение '{match.group()}' при отклонении {diff:.1f}% < 50%"]
    return []


def check_deviation_level_used(verdict: str, calc: MetricCalculations) -> list:
    # Уровень по отраслевым порогам должен быть упомянут дословно
    level = calc.extra.get("deviation_level", "")
    if level and level not in verdict:
        return [f"Уровень '{level}' не упомянут дословно"]
    return []


def check_magnitude_label_used(verdict: str, calc: MetricCalculations) -> list:
    # Характеристика отклонения должна присутствовать в тексте
    label = calc.extra.get("magnitude_label", "")
    if label and label not in verdict:
        return [f"Характеристика отклонения '{label}' не использована"]
    return []


#  Проверки для Метрики 2 (direct_losses_dynamics)

def check_divergence_label_used(verdict: str, calc: MetricCalculations) -> list:
    # Характеристика расхождения должна быть в открывающем предложении.
    # Проверяем по корню слова, так как в эталонах встречаются и единственное,
    # и множественное число: «отличается» / «отличаются», «совпадает» / «совпадают»
    label = calc.extra.get("divergence_label", "")
    if not label:
        return []

    # Извлекаем ключевое слово (отлич/совпад/незначительн/несколько/драматичн/существенн)
    stems = ["отлич", "совпад", "незначительн", "несколько", "драматичн", "существенн"]
    label_lower = label.lower()
    verdict_lower = verdict.lower()

    # Если хотя бы один корень из label есть в verdict — считаем что использован
    label_stems = [s for s in stems if s in label_lower]
    if label_stems and any(s in verdict_lower for s in label_stems):
        return []

    return [f"Характеристика расхождения '{label}' не использована"]


def check_last_quarter_mentioned(verdict: str, calc: MetricCalculations) -> list:
    # Последний квартал должен быть назван (формат "Q3 2025")
    label = calc.extra.get("last_quarter_label", "")
    if label and label not in verdict:
        return [f"Последний квартал '{label}' не упомянут"]
    return []


def check_ratios_present(verdict: str, calc: MetricCalculations) -> list:
    # В тексте должны быть оба коэффициента: за 4 квартала и за последний квартал
    errors = []
    last_4q = calc.extra.get("last_4q_factor_fmt", "")
    last_q = calc.extra.get("last_q_factor_fmt", "")
    if last_4q and last_4q not in verdict:
        errors.append(f"Коэффициент за 4 квартала '{last_4q}' не упомянут")
    if last_q and last_q not in verdict:
        errors.append(f"Коэффициент за последний квартал '{last_q}' не упомянут")
    return errors


def check_trend_direction(verdict: str, calc: MetricCalculations) -> list:
    # Направление тренда банка не должно противоречить данным
    bank_trend = calc.extra.get("bank_trend_3q", "")
    text = verdict.lower()

    # Если в данных «рост», в тексте не должно быть «снижается/падает»
    if "рост" in bank_trend and re.search(r'(?:снижени[ея]|сниж[аи]|пад[аеи]|спад)', text):
        return [f"Противоречие тренда: данные '{bank_trend}', текст говорит о снижении"]
    if "снижение" in bank_trend and re.search(r'(?:рост|увеличени[ея]|растёт|растет)', text):
        # Исключение: текст может говорить «рост рынка», поэтому проверяем контекст «вашего банка»
        if re.search(r'ваш[а-я]*\s+банк[а-я]*.{0,40}(?:рост|увеличени|растёт|растет)', text):
            return [f"Противоречие тренда: данные '{bank_trend}', текст говорит о росте банка"]
    return []


# Главный класс 

class Evaluator:

    # Универсальные проверки — применяются ко всем метрикам
    UNIVERSAL_CHECKS = [
        check_min_length,
        check_english_words,
        check_forbidden_words,
        check_hallucinated_numbers,
    ]

    # Специфичные проверки по типу метрики
    METRIC_CHECKS = {
        "loss_share": [
            check_direction_loss_share,
            check_position_mentioned,
            check_extreme_mention,
            check_exaggeration,
            check_deviation_level_used,
            check_magnitude_label_used,
        ],
        "direct_losses_dynamics": [
            check_divergence_label_used,
            check_last_quarter_mentioned,
            check_ratios_present,
            check_trend_direction,
        ],
    }

    def evaluate(self, verdict: str, calc: MetricCalculations) -> tuple:
        # Возвращает (passed, score, errors)
        errors = []

        # Универсальные проверки
        for fn in self.UNIVERSAL_CHECKS:
            errors.extend(fn(verdict, calc))

        # Специфичные проверки для текущей метрики
        for fn in self.METRIC_CHECKS.get(calc.metric_type, []):
            errors.extend(fn(verdict, calc))

        passed = len(errors) == 0
        score = max(0.0, 1.0 - 0.15 * len(errors))
        return passed, round(score, 2), errors


# Helpers 

def _number_variants(val: float) -> set:
    # Все допустимые варианты записи числа (округления, запятая вместо точки)
    variants = set()
    abs_val = abs(val)

    for nd in range(4):
        rounded = round(abs_val, nd)
        s = f"{rounded:.{nd}f}"
        stripped = s.rstrip('0').rstrip('.') if '.' in s else s
        for variant in [s, stripped]:
            variants.add(variant)
            variants.add(variant.replace('.', ','))

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
            pass

    if val < 0:
        variants.update(_number_variants(abs_val))
    return variants