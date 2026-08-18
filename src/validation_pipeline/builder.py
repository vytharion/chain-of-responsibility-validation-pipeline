from __future__ import annotations

from typing import Any, Optional

from validation_pipeline.handler import Handler
from validation_pipeline.result import ValidationResult
from validation_pipeline.validators import PresenceHandler, RangeHandler, TypeHandler


class ChainBuilder:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def add(self, handler: Handler) -> "ChainBuilder":
        if not isinstance(handler, Handler):
            raise TypeError("ChainBuilder.add expects a Handler instance")
        if handler in self._handlers:
            raise ValueError("the same handler instance cannot be added twice")
        self._handlers.append(handler)
        return self

    def presence(self, field: str) -> "ChainBuilder":
        return self.add(PresenceHandler(field))

    def type_of(self, field: str, expected: type) -> "ChainBuilder":
        return self.add(TypeHandler(field, expected))

    def range_of(self, field: str, minimum: float, maximum: float) -> "ChainBuilder":
        return self.add(RangeHandler(field, minimum, maximum))

    def __len__(self) -> int:
        return len(self._handlers)

    def build(self) -> Handler:
        if not self._handlers:
            raise ValueError("cannot build an empty chain")
        head = self._handlers[0]
        self._reset_links()
        self._link_pairs()
        return head

    def run(self, payload: Any) -> Optional[ValidationResult]:
        head = self.build()
        return head.handle(payload)

    def _reset_links(self) -> None:
        for handler in self._handlers:
            handler._next = None

    def _link_pairs(self) -> None:
        previous = self._handlers[0]
        for current in self._handlers[1:]:
            previous.set_next(current)
            previous = current
