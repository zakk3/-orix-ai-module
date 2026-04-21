# src/core/validation/input_validator.py

from typing import Dict, Any, List, Tuple


MY_BANK_KEYWORDS = ("мой банк", "my bank", "мой_банк")
AVERAGE_KEYWORDS = ("среднее", "average", "mean", "среднее по кластеру")


class InputValidator:

    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not isinstance(data, dict):
            return False, [f"Ожидался dict, получено: {type(data).__name__}"]

        if "series" not in data:
            return False, ["Отсутствует поле 'series'"]

        series = data["series"]

        if not isinstance(series, list):
            return False, [f"'series' должен быть списком, получено: {type(series).__name__}"]

        if len(series) < 2:
            return False, [f"'series' должен содержать минимум 2 элемента, получено: {len(series)}"]

        for i, item in enumerate(series):
            errors.extend(self._check_item(item, i))

        # проверяем наличие Мой банк или формата временных рядов
        if not self._has_my_bank(series) and not self._is_timeseries(series):
            errors.append("Нет элемента 'Мой банк' и нет полей 'self'/'rest'")

        # avg должен быть числом если передан
        if "avg" in data and data["avg"] is not None:
            if not isinstance(data["avg"], (int, float)):
                errors.append(f"'avg' должен быть числом, получено: {type(data['avg']).__name__}")

        return len(errors) == 0, errors

    def _check_item(self, item: Any, index: int) -> List[str]:
        errors: List[str] = []

        if not isinstance(item, dict):
            return [f"series[{index}]: ожидался объект, получено {type(item).__name__}"]

        if "serie" not in item:
            errors.append(f"series[{index}]: нет поля 'serie'")
        if "label" not in item:
            errors.append(f"series[{index}]: нет поля 'label'")

        # должно быть хотя бы одно числовое поле
        has_any = any(item.get(f) is not None for f in ("value", "self", "rest"))
        if not has_any:
            errors.append(f"series[{index}]: нет ни одного из полей value/self/rest")

        for field in ("value", "self", "rest"):
            val = item.get(field)
            if val is not None and not isinstance(val, (int, float)):
                errors.append(f"series[{index}].{field}: ожидалось число, получено {type(val).__name__}")

        return errors

    @staticmethod
    def _has_my_bank(series: List[Dict[str, Any]]) -> bool:
        for item in series:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).lower()
            if any(kw in label for kw in MY_BANK_KEYWORDS):
                return True
        return False

    @staticmethod
    def _is_timeseries(series: List[Dict[str, Any]]) -> bool:
        for item in series:
            if not isinstance(item, dict):
                continue
            if item.get("self") is not None and item.get("rest") is not None:
                return True
        return False