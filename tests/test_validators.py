from __future__ import annotations

import pytest

from validation_pipeline import (
    Handler,
    PresenceHandler,
    RangeHandler,
    TypeHandler,
    ValidationResult,
)


class TestPresenceHandler:
    def test_forwards_when_field_present_and_non_none(self) -> None:
        handler = PresenceHandler("email")
        assert handler.handle({"email": "vy@example.com"}) is None

    def test_reports_failure_when_field_missing(self) -> None:
        handler = PresenceHandler("email")
        result = handler.handle({"name": "Vy"})
        assert result is not None
        assert result.ok is False
        assert result.handler == "presence[email]"
        assert "'email' is required" in (result.error or "")

    def test_none_value_is_treated_as_missing(self) -> None:
        handler = PresenceHandler("email")
        result = handler.handle({"email": None})
        assert result is not None
        assert result.ok is False
        assert "'email' is required" in (result.error or "")

    def test_empty_string_is_present(self) -> None:
        handler = PresenceHandler("email")
        assert handler.handle({"email": ""}) is None

    def test_non_mapping_payload_is_rejected(self) -> None:
        handler = PresenceHandler("email")
        result = handler.handle("not a mapping")
        assert result is not None
        assert result.ok is False
        assert "mapping" in (result.error or "")

    def test_empty_field_name_is_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="field name"):
            PresenceHandler("")


class TestTypeHandler:
    def test_forwards_when_value_matches_expected_type(self) -> None:
        handler = TypeHandler("age", int)
        assert handler.handle({"age": 30}) is None

    def test_reports_failure_on_wrong_type(self) -> None:
        handler = TypeHandler("age", int)
        result = handler.handle({"age": "thirty"})
        assert result is not None
        assert result.ok is False
        assert result.handler == "type[age:int]"
        assert "expected int" in (result.error or "")
        assert "got str" in (result.error or "")

    def test_missing_field_is_forwarded_not_failed(self) -> None:
        handler = TypeHandler("age", int)
        assert handler.handle({"name": "Vy"}) is None

    def test_non_mapping_payload_is_forwarded(self) -> None:
        handler = TypeHandler("age", int)
        assert handler.handle(42) is None

    def test_non_type_expected_argument_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="expected must be a type"):
            TypeHandler("age", "int")  # type: ignore[arg-type]


class TestRangeHandler:
    def test_forwards_when_value_is_inside_range(self) -> None:
        handler = RangeHandler("age", 0, 120)
        assert handler.handle({"age": 30}) is None

    def test_forwards_at_boundaries(self) -> None:
        handler = RangeHandler("age", 0, 120)
        assert handler.handle({"age": 0}) is None
        assert handler.handle({"age": 120}) is None

    def test_reports_failure_when_value_below_minimum(self) -> None:
        handler = RangeHandler("age", 0, 120)
        result = handler.handle({"age": -1})
        assert result is not None
        assert result.ok is False
        assert result.handler == "range[age:0..120]"
        assert "-1" in (result.error or "")
        assert "not in" in (result.error or "")

    def test_reports_failure_when_value_above_maximum(self) -> None:
        handler = RangeHandler("age", 0, 120)
        result = handler.handle({"age": 121})
        assert result is not None
        assert result.ok is False
        assert "121" in (result.error or "")

    def test_missing_field_is_forwarded(self) -> None:
        handler = RangeHandler("age", 0, 120)
        assert handler.handle({"name": "Vy"}) is None

    def test_non_numeric_value_is_forwarded_not_failed(self) -> None:
        handler = RangeHandler("age", 0, 120)
        assert handler.handle({"age": "thirty"}) is None

    def test_boolean_is_not_treated_as_numeric(self) -> None:
        handler = RangeHandler("age", 0, 120)
        assert handler.handle({"age": True}) is None

    def test_float_value_inside_range_passes(self) -> None:
        handler = RangeHandler("score", 0.0, 1.0)
        assert handler.handle({"score": 0.75}) is None

    def test_inverted_bounds_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="minimum cannot exceed maximum"):
            RangeHandler("age", 120, 0)


class TestValidatorsInChain:
    def test_full_chain_all_pass_returns_none(self) -> None:
        presence = PresenceHandler("age")
        type_check = TypeHandler("age", int)
        range_check = RangeHandler("age", 0, 120)
        presence.set_next(type_check).set_next(range_check)

        assert presence.handle({"age": 30}) is None

    def test_chain_short_circuits_on_first_failure(self) -> None:
        presence = PresenceHandler("age")
        type_check = TypeHandler("age", int)
        range_check = RangeHandler("age", 0, 120)
        presence.set_next(type_check).set_next(range_check)

        result = presence.handle({})
        assert result is not None
        assert result.ok is False
        assert result.handler == "presence[age]"

    def test_type_failure_prevents_range_check(self) -> None:
        presence = PresenceHandler("age")
        type_check = TypeHandler("age", int)
        range_check = RangeHandler("age", 0, 120)
        presence.set_next(type_check).set_next(range_check)

        result = presence.handle({"age": "old"})
        assert result is not None
        assert result.ok is False
        assert result.handler == "type[age:int]"

    def test_range_failure_reported_when_upstream_passes(self) -> None:
        presence = PresenceHandler("age")
        type_check = TypeHandler("age", int)
        range_check = RangeHandler("age", 0, 120)
        presence.set_next(type_check).set_next(range_check)

        result = presence.handle({"age": 999})
        assert result is not None
        assert result.ok is False
        assert result.handler == "range[age:0..120]"

    def test_all_validators_are_handler_subclasses(self) -> None:
        assert issubclass(PresenceHandler, Handler)
        assert issubclass(TypeHandler, Handler)
        assert issubclass(RangeHandler, Handler)

    def test_success_verdict_from_terminal_handler(self) -> None:
        # A trailing handler that always returns a success verdict
        # confirms the chain can also produce ok=True outcomes.
        class Approver(Handler):
            def handle(self, payload: object) -> ValidationResult:
                return ValidationResult.success("approver")

        presence = PresenceHandler("age")
        presence.set_next(Approver())
        outcome = presence.handle({"age": 25})
        assert outcome is not None
        assert outcome.ok is True
        assert outcome.handler == "approver"
