from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    SHORT_CIRCUIT = "short_circuit"
    COLLECT_ALL = "collect_all"
