# src/golden_set/golden_set_manager.py
# Загружает эталонные примеры из JSON-файлов для few-shot prompting.
# Используется в NLGGenerator при сборке промпта для LLM.

import json
import os
from typing import List, Dict, Any

# Папка с JSON-файлами эталонов — рядом с этим файлом
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Маппинг: код метрики → имя JSON-файла
METRIC_FILES = {
    "loss_share":              "metric1.json",
    "direct_losses_dynamics":  "metric2.json",
    "net_losses_dynamics":     "metric3.json",
    "recovery_level":          "metric4.json",
    "concentration":           "metric5.json",
    "kpur_violation":          "metric6.json",
}


class GoldenSetManager:
    """Управляет базой эталонных примеров для few-shot learning."""

    def __init__(self) -> None:
        # Кэш: не читаем файл при каждом запросе
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_examples(self, metric_type: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Вернуть список эталонных примеров для метрики.
        limit — сколько примеров передать в промпт (обычно 3).
        """
        if metric_type not in self._cache:
            self._cache[metric_type] = self._load(metric_type)

        return self._cache[metric_type][:limit]

    def add_example(self, metric_type: str, example: Dict[str, Any]) -> None:
        """
        Добавить новый пример в Golden Set.
        Используется для расширения набора на основе обратной связи.
        """
        examples = self._load(metric_type)
        examples.append(example)

        path = self._get_path(metric_type)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"metric": metric_type, "examples": examples},
                      f, ensure_ascii=False, indent=2)

        # Сбрасываем кэш чтобы подтянуть новый пример
        self._cache.pop(metric_type, None)

    def count(self, metric_type: str) -> int:
        """Сколько примеров есть для данной метрики."""
        return len(self._load(metric_type))

    # ── внутренние методы ──────────────────────────────────────────────────

    def _load(self, metric_type: str) -> List[Dict[str, Any]]:
        """Читаем JSON-файл с эталонами."""
        path = self._get_path(metric_type)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("examples", [])

    @staticmethod
    def _get_path(metric_type: str) -> str:
        """Путь к JSON-файлу для данной метрики."""
        filename = METRIC_FILES.get(metric_type)
        if not filename:
            raise ValueError(f"Неизвестная метрика: '{metric_type}'")
        return os.path.join(DATA_DIR, filename)