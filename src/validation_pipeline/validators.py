from __future__ import annotations

import re
from collections.abc import Mapping
from numbers import Real
from typing import Any, Optional, Pattern, Union

from validation_pipeline.handler import Handler
from validation_pipeline.result import ValidationResult


class PresenceHandler(Handler):
    def __init__(self, field: str) -> None:
        super().__init__()
        if not field:
            raise ValueError("field name must be a non-empty string")
        self.field = field

    @property
    def name(self) -> str:
        return f"presence[{self.field}]"

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        if not isinstance(payload, Mapping):
            return ValidationResult.failure(self.name, "payload must be a mapping")
        if self.field not in payload or payload[self.field] is None:
            return ValidationResult.failure(
                self.name, f"field '{self.field}' is required"
            )
        return self._forward(payload)


class TypeHandler(Handler):
    def __init__(self, field: str, expected: type) -> None:
        super().__init__()
        if not field:
            raise ValueError("field name must be a non-empty string")
        if not isinstance(expected, type):
            raise TypeError("expected must be a type")
        self.field = field
        self.expected = expected

    @property
    def name(self) -> str:
        return f"type[{self.field}:{self.expected.__name__}]"

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        if not isinstance(payload, Mapping) or self.field not in payload:
            return self._forward(payload)
        value = payload[self.field]
        if not isinstance(value, self.expected):
            return ValidationResult.failure(
                self.name,
                f"field '{self.field}' expected {self.expected.__name__}, "
                f"got {type(value).__name__}",
            )
        return self._forward(payload)


class RangeHandler(Handler):
    def __init__(self, field: str, minimum: float, maximum: float) -> None:
        super().__init__()
        if not field:
            raise ValueError("field name must be a non-empty string")
        if minimum > maximum:
            raise ValueError("minimum cannot exceed maximum")
        self.field = field
        self.minimum = minimum
        self.maximum = maximum

    @property
    def name(self) -> str:
        return f"range[{self.field}:{self.minimum}..{self.maximum}]"

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        if not isinstance(payload, Mapping) or self.field not in payload:
            return self._forward(payload)
        value = payload[self.field]
        if not isinstance(value, Real) or isinstance(value, bool):
            return self._forward(payload)
        if not (self.minimum <= value <= self.maximum):
            return ValidationResult.failure(
                self.name,
                f"field '{self.field}' = {value} not in "
                f"[{self.minimum}, {self.maximum}]",
            )
        return self._forward(payload)


class MinLengthHandler(Handler):
    def __init__(self, field: str, minimum: int) -> None:
        super().__init__()
        if not field:
            raise ValueError("field name must be a non-empty string")
        if minimum < 0:
            raise ValueError("minimum length cannot be negative")
        self.field = field
        self.minimum = minimum

    @property
    def name(self) -> str:
        return f"min_length[{self.field}:{self.minimum}]"

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        if not isinstance(payload, Mapping) or self.field not in payload:
            return self._forward(payload)
        value = payload[self.field]
        if not isinstance(value, str):
            return self._forward(payload)
        if len(value) < self.minimum:
            return ValidationResult.failure(
                self.name,
                f"field '{self.field}' length {len(value)} is below minimum {self.minimum}",
            )
        return self._forward(payload)


class PatternHandler(Handler):
    def __init__(
        self,
        field: str,
        pattern: Union[str, Pattern[str]],
        label: Optional[str] = None,
    ) -> None:
        super().__init__()
        if not field:
            raise ValueError("field name must be a non-empty string")
        self.field = field
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.label = label or "pattern"

    @property
    def name(self) -> str:
        return f"pattern[{self.field}:{self.label}]"

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        if not isinstance(payload, Mapping) or self.field not in payload:
            return self._forward(payload)
        value = payload[self.field]
        if not isinstance(value, str):
            return self._forward(payload)
        if self.pattern.fullmatch(value) is None:
            return ValidationResult.failure(
                self.name,
                f"field '{self.field}' does not match {self.label}",
            )
        return self._forward(payload)
