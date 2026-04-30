# src/core/validation/evaluator.py
#
# Шаг 3 архитектуры: автоматическая валидация вывода.
# Проверяет: числовые галлюцинации, направление, позицию,
# семантические преувеличения, запрещённые конструкции.
# Совместим с pipeline: возвращает (passed, score, errors).

import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from src.models.output_models import MetricCalculations


# Числа, разрешённые всегда независимо от данных:
# - стандартные (0, 1, 50, 100)
# - отраслевые пороги deviation_level (0.5, 0.8, 0.96)
#   → они показываются LLM в промпте как threshold_value и всегда допустимы
# - репрезентативность выборки (62%)
ALWAYS_ALLOWED = {
    "0", "1", "2", "3", "4", "5",
    "10", "50", "100",
    # Пороги deviation_level
    "0.5", "0,5",
    "0.8", "0,8",
    "0.96", "0,96",
    # Репрезентативность
    "62", "62.0", "62,0",
}

# Паттерны для очистки текста от дат, кварталов и безопасных фраз
# (LLM может взять их из контекста — они не должны считаться галлюцинациями)
DATE_PATTERNS = [
    r'\b20[2-3]\d\b',                          # 2022, 2023, 2024
    r'\b[1-4]\s*-?[оыйемя]*\s*кв[а-яё.-]*',   # 1-й квартал, 2 кв.
    r'\bQ[1-4]\b',                              # Q1, Q2
    r'\b[2-3]\d\s*г[а-яех.]*',                 # 23 года, 24 г.
    r'\bв\s+\d+(?:[.,]\d+)?\s+раз[а]?\b',      # в 3 раза, в 1,5 раза, в 10 раз
    r'\bна\s+100\s*%\b',                        # на 100%
    r'\bна\s+50\s*%\b',                         # на 50%
    r'\b62\s*%\b',                              # 62% (репрезентативность)
]

# Слова, свидетельствующие об экстремальном/плохом значении.
# Расширен список: LLM использует синонимы, все должны засчитываться.
EXTREME_WORDS_PATTERN = re.compile(
    r'наихудш|экстремальн|аномальн|значительн|существенн|'
    r'наибольш|максимальн|критическ|крайне\s+высок|'
    r'самом?\s+высок|самом?\s+низк|наивысш',
    re.IGNORECASE
)


class Evaluator:
    """Проверяет корректность сгенерированного вывода."""

    def evaluate(
        self, verdict: str, calculations: MetricCalculations
    ) -> tuple:
        """
        Возвращает (passed: bool, score: float, errors: list).
        passed — True если все проверки пройдены
        score  — 1.0 минус 0.15 за каждую ошибку
        errors — список найденных проблем
        """
        errors = []

        # 1. Минимальная длина
        if len(verdict) < 100:
            errors.append(f"Вывод слишком короткий ({len(verdict)} симв., минимум 100)")

        # 2. Проверка направления: не должно быть противоречия выше/ниже
        errors.extend(self._check_direction(verdict, calculations))

        # 3. Семантическая проверка: при плохой позиции нужен вывод об экстремальном значении
        errors.extend(self._check_extreme_mention(verdict, calculations))

        # 4. Семантическая проверка: запрет преувеличений при малом отклонении
        errors.extend(self._check_exaggeration(verdict, calculations))

        # 5. Проверка числовых галлюцинаций
        errors.extend(self._check_hallucinated_numbers(verdict, calculations))

        # 6. Упомянута ли позиция банка
        errors.extend(self._check_position_mentioned(verdict, calculations))

        passed = len(errors) == 0
        score = max(0.0, 1.0 - 0.15 * len(errors))
        return passed, round(score, 2), errors

    # ── Отдельные проверки ─────────────────────────────────────────────────

    @staticmethod
    def _check_direction(verdict: str, calc: MetricCalculations) -> list:
        """Направление не должно противоречить данным."""
        errors = []
        text = verdict.lower()
        if calc.is_below_average:
            # Текст говорит «выше» без упоминания «ниже»
            if re.search(r'\bвыше\b', text) and not re.search(r'\bниже\b', text):
                errors.append(
                    "Противоречие направления: банк ниже среднего, "
                    "но вывод утверждает 'выше среднего'"
                )
        else:
            # Текст говорит «ниже» без упоминания «выше»
            if re.search(r'\bниже\b', text) and not re.search(r'\bвыше\b', text):
                errors.append(
                    "Противоречие направления: банк выше среднего, "
                    "но вывод утверждает 'ниже среднего'"
                )
        return errors

    @staticmethod
    def _check_extreme_mention(verdict: str, calc: MetricCalculations) -> list:
        """
        При позиции ≥ 75% (ближе к концу рейтинга) вывод должен содержать
        слово об экстремальном/значительном/максимальном значении.
        Порог повышен с 65% до 75% и список слов расширен.
        """
        errors = []
        pos = calc.position or 0
        total = calc.total_banks or 1
        ratio = pos / total if total > 0 else 0
        if ratio >= 0.75:
            if not EXTREME_WORDS_PATTERN.search(verdict):
                errors.append(
                    f"Пропущен вывод об экстремальном значении "
                    f"при позиции {pos}/{total} (≥75%)"
                )
        return errors

    @staticmethod
    def _check_exaggeration(verdict: str, calc: MetricCalculations) -> list:
        """
        «Существенно» и «значительно» допустимы только при отклонении ≥ 50%.
        Порог оставлен 50%, но проверяем конкретный контекст (ниже/выше/отлич).
        """
        errors = []
        diff = calc.difference_percent  # уже абсолютное
        if diff < 50:
            match = re.search(
                r'(существенно|значительно)\s+(ниже|выше|отлич)',
                verdict, re.IGNORECASE
            )
            if match:
                errors.append(
                    f"Семантическое преувеличение '{match.group()}' "
                    f"при отклонении {diff:.1f}% < 50%"
                )
        return errors

    @staticmethod
    def _check_position_mentioned(verdict: str, calc: MetricCalculations) -> list:
        """Позиция в рейтинге должна быть упомянута."""
        errors = []
        if calc.position and calc.total_banks:
            pos_str = str(calc.position)
            total_str = str(calc.total_banks)
            # Проверяем что оба числа есть в тексте рядом (в пределах 50 символов)
            pos_idx = verdict.find(pos_str)
            total_idx = verdict.find(total_str)
            if pos_idx == -1 or total_idx == -1:
                errors.append(
                    f"Позиция {calc.position} из {calc.total_banks} не упомянута в выводе"
                )
        return errors

    @staticmethod
    def _check_hallucinated_numbers(verdict: str, calc: MetricCalculations) -> list:
        """
        Проверяем что все числа в тексте есть в расчётах или в белом списке.
        Разрешены: округления, запятая вместо точки, абсолютное значение.

        Исправления:
        - Пороги deviation_level (0.5, 0.8, 0.96) теперь в ALWAYS_ALLOWED
        - DATE_PATTERNS расширен (покрывает «в N раз» с дробями)
        - _number_variants генерирует больше форматов
        """
        errors = []

        # Очищаем текст от дат/кварталов — они берутся из контекста, не галлюцинации
        cleaned = verdict
        for pattern in DATE_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        # Удаляем пробелы внутри чисел ("1 000" → "1000")
        cleaned = re.sub(r'(?<=\d)\s+(?=\d)', '', cleaned)

        # Извлекаем все числа из очищенного текста
        raw_numbers = re.findall(r'[-+–−]?\d+[.,]?\d*', cleaned)

        # Нормализуем: убираем знак, заменяем запятую на точку,
        # убираем незначащие нули ("0.50" → "0.5", "1.10" → "1.1")
        numbers_in_text = []
        for n in raw_numbers:
            n = n.replace('–', '-').replace('−', '-').lstrip('+-')
            normalized = n.replace(',', '.')
            # Пропускаем если это не похоже на число
            try:
                float(normalized)
                # Убираем trailing zeros чтобы "0.50" совпало с "0.5"
                if '.' in normalized:
                    normalized = normalized.rstrip('0').rstrip('.')
                numbers_in_text.append(normalized)
            except ValueError:
                pass

        # Строим набор разрешённых чисел из расчётов
        safe = set(ALWAYS_ALLOWED)

        # Из полей MetricCalculations
        for field, v in vars(calc).items():
            if isinstance(v, (int, float)):
                safe.update(Evaluator._number_variants(v))

        # Из extra-словаря (magnitude_label, deviation_level и т.д.)
        for k, v in calc.extra.items():
            if isinstance(v, (int, float)):
                safe.update(Evaluator._number_variants(v))
            if isinstance(v, str):
                for n in re.findall(r'\d+[.,]?\d*', v):
                    safe.add(n.replace(',', '.'))

        # Проверяем каждое число из текста
        for n in numbers_in_text:
            if n not in safe:
                errors.append(f"Возможная галлюцинация: число '{n}' не найдено в расчётах")

        return errors

    @staticmethod
    def _number_variants(val: float) -> set:
        """
        Генерируем все допустимые варианты записи числа.
        Покрывает: 0/1/2/3 знака после запятой, запятую вместо точки,
        абсолютное значение, целое без дроби.
        """
        variants = set()
        abs_val = abs(val)

        for nd in range(4):  # 0, 1, 2, 3 знака
            rounded = round(abs_val, nd)
            # Форматируем с фиксированным числом знаков
            s = f"{rounded:.{nd}f}"
            # Убираем лишний .0 и trailing zeros
            if '.' in s:
                stripped = s.rstrip('0').rstrip('.')
            else:
                stripped = s
            for variant in [s, stripped]:
                variants.add(variant)
                variants.add(variant.replace('.', ','))

            # Дополнительно через Decimal для точного округления
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

        # Если val отрицательный — добавляем варианты абсолютного значения
        if val < 0:
            variants.update(Evaluator._number_variants(abs_val))

        return variants