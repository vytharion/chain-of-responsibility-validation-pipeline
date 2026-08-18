from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from validation_pipeline.result import ValidationResult


class Handler(ABC):
    def __init__(self) -> None:
        self._next: Optional[Handler] = None

    def set_next(self, handler: "Handler") -> "Handler":
        if handler is self:
            raise ValueError("a handler cannot point to itself as the next link")
        self._next = handler
        return handler

    @property
    def next_handler(self) -> Optional["Handler"]:
        return self._next

    @abstractmethod
    def handle(self, payload: Any) -> Optional[ValidationResult]:
        ...

    def _forward(self, payload: Any) -> Optional[ValidationResult]:
        if self._next is None:
            return None
        return self._next.handle(payload)
