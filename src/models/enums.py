# src/models/enums.py
# порядок метрик строго по ТЗ пп.1-6, не менять

from enum import Enum


class MetricType(str, Enum):
    LOSS_SHARE             = "loss_share"
    DIRECT_LOSSES_DYNAMICS = "direct_losses_dynamics"
    NET_LOSSES_DYNAMICS    = "net_losses_dynamics"
    RECOVERY_LEVEL         = "recovery_level"
    CONCENTRATION          = "concentration"
    KPUR_VIOLATION         = "kpur_violation"


class DeviationThreshold(str, Enum):
    # пороги взяты из Golden Set Орикс
    INSIGNIFICANT = "незначительное"  # < 10%
    MODERATE      = "среднее"         # 10–30%
    SIGNIFICANT   = "существенное"    # > 30%


class DeviationDirection(str, Enum):
    BELOW = "ниже"
    ABOVE = "выше"
    EQUAL = "соответствует"


class Scenario(str, Enum):
    # используется для маркировки примеров в Golden Set
    NORMAL       = "normal"
    BELOW_AVERAGE = "below_average"
    ABOVE_AVERAGE = "above_average"
    CRITICAL     = "critical"