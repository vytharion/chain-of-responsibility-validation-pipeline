from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional

from validation_pipeline.builder import ChainBuilder
from validation_pipeline.execution import ExecutionMode
from validation_pipeline.result import ValidationResult

EMAIL_PATTERN = r"[^@\s]+@[^@\s]+\.[^@\s]+"

_PASSWORD_MIN_LENGTH = 8
_DISPLAY_NAME_MIN_LENGTH = 2
_MIN_AGE = 13
_MAX_AGE = 120
_REGISTRATION_FIELDS = ("email", "password", "display_name", "age")


@dataclass(frozen=True, slots=True)
class RegistrationOutcome:
    accepted: bool
    errors: tuple[ValidationResult, ...] = field(default_factory=tuple)
    normalized: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if self.accepted and self.errors:
            raise ValueError("an accepted registration cannot carry errors")
        if not self.accepted and not self.errors:
            raise ValueError("a rejected registration must carry at least one error")
        if self.accepted and self.normalized is None:
            raise ValueError("an accepted registration must carry a normalized payload")

    @classmethod
    def accept(cls, normalized: Mapping[str, Any]) -> "RegistrationOutcome":
        return cls(accepted=True, errors=(), normalized=dict(normalized))

    @classmethod
    def reject(cls, errors: list[ValidationResult]) -> "RegistrationOutcome":
        if not errors:
            raise ValueError("reject() requires at least one error")
        return cls(accepted=False, errors=tuple(errors), normalized=None)

    @property
    def error_messages(self) -> tuple[str, ...]:
        return tuple(e.error or "" for e in self.errors)


def build_registration_chain() -> ChainBuilder:
    return (
        ChainBuilder()
        .presence("email")
        .type_of("email", str)
        .pattern("email", EMAIL_PATTERN, "email")
        .presence("password")
        .type_of("password", str)
        .min_length("password", _PASSWORD_MIN_LENGTH)
        .presence("display_name")
        .type_of("display_name", str)
        .min_length("display_name", _DISPLAY_NAME_MIN_LENGTH)
        .presence("age")
        .type_of("age", int)
        .range_of("age", _MIN_AGE, _MAX_AGE)
    )


def register_user(
    payload: Mapping[str, Any],
    mode: ExecutionMode = ExecutionMode.COLLECT_ALL,
    chain: Optional[ChainBuilder] = None,
) -> RegistrationOutcome:
    active_chain = chain if chain is not None else build_registration_chain()
    normalized = _normalize(payload)
    failures = active_chain.execute(normalized, mode=mode)
    if failures:
        return RegistrationOutcome.reject(failures)
    return RegistrationOutcome.accept(normalized)


def _normalize(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[key] = _normalize_value(key, value)
    return normalized


def _normalize_value(key: str, value: Any) -> Any:
    if key == "email" and isinstance(value, str):
        return value.strip().lower()
    if key == "display_name" and isinstance(value, str):
        return value.strip()
    return value
