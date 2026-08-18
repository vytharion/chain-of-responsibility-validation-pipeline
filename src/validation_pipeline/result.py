from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    handler: str
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.handler:
            raise ValueError("handler name must be a non-empty string")
        if self.ok and self.error is not None:
            raise ValueError("a successful result cannot carry an error message")
        if not self.ok and not self.error:
            raise ValueError("a failed result must carry an error message")

    @classmethod
    def success(cls, handler: str) -> "ValidationResult":
        return cls(ok=True, handler=handler, error=None)

    @classmethod
    def failure(cls, handler: str, error: str) -> "ValidationResult":
        return cls(ok=False, handler=handler, error=error)
