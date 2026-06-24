# src/golden_set/golden_set_manager.py
# Загружает эталонные примеры из JSON-файлов для few-shot prompting.
# Используется в NLGGenerator при сборке промпта для LLM.

import json
import os
from typing import List, Dict, Any, Optional

# Папка с JSON-файлами эталонов — рядом с этим файлом
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Маппинг: код метрики - имя JSON-файла
METRIC_FILES = {
    "loss_share":              "metric1.json",
    "direct_losses_dynamics":  "metric2.json",
    "loss_buckets":            "metric3.json",
    "net_losses_dynamics":     "metric3.json",
    "recovery_level":          "metric4.json",
    "concentration":           "metric5.json",
    "kpur_violation":          "metric6.json",
}


class GoldenSetManager:
    """Управляет базой эталонных примеров для few-shot learning."""

    def __init__(self) -> None:
        self._cache = {}

    def get_examples(self, metric_type, limit = 3):
        """
        Вернуть список эталонных примеров для метрики.
        limit — сколько примеров передать в промпт (обычно 3).
        """
        if metric_type not in self._cache:
            self._cache[metric_type] = self._load(metric_type)

        return self._cache[metric_type][:limit]

    def get_examples_for_scenario(
        self,
        metric_type: str,
        match_field: str,
        match_value: Optional[str],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Вернуть пример(ы), у которых example[match_field] == match_value —
        то есть пример того же сценария/категории, что и текущий расчёт.

        Так каждый сценарий («совпадают» / «незначительно отличаются» / ...)
        показывает LLM СВОЙ собственный эталон стиля
        """
        if metric_type not in self._cache:
            self._cache[metric_type] = self._load(metric_type)

        pool = self._cache[metric_type]
        if match_value is not None:
            matching = [ex for ex in pool if ex.get(match_field) == match_value]
            if matching:
                return matching[:limit]

        # Запасной вариант: нет эталона для этого сценария — берём первые
        return pool[:limit]

    def add_example(self, metric_type, example):
        """Добавить новый пример в Golden Set."""
        examples = self._load(metric_type)
        examples.append(example)

        path = self._get_path(metric_type)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"metric": metric_type, "examples": examples},
                      f, ensure_ascii=False, indent=2)

        self._cache.pop(metric_type, None)

    def count(self, metric_type):
        """Сколько примеров есть для данной метрики."""
        return len(self._load(metric_type))

    def _load(self, metric_type):
        """Читаем JSON-файл с эталонами."""
        path = self._get_path(metric_type)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("examples", [])

    @staticmethod
    def _get_path(metric_type):
        """Путь к JSON-файлу для данной метрики."""
        filename = METRIC_FILES.get(metric_type)
        if not filename:
            raise ValueError(f"Неизвестная метрика: '{metric_type}'")
        return os.path.join(DATA_DIR, filename)
