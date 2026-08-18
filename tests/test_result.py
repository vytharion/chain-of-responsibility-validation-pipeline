from dataclasses import FrozenInstanceError

import pytest

from validation_pipeline import ValidationResult


class TestSuccessFactory:
    def test_success_marks_ok_true(self) -> None:
        result = ValidationResult.success("presence")
        assert result.ok is True
        assert result.handler == "presence"
        assert result.error is None

    def test_success_via_direct_construction(self) -> None:
        result = ValidationResult(ok=True, handler="type")
        assert result.ok is True
        assert result.error is None


class TestFailureFactory:
    def test_failure_marks_ok_false(self) -> None:
        result = ValidationResult.failure("range", "value out of bounds")
        assert result.ok is False
        assert result.handler == "range"
        assert result.error == "value out of bounds"

    def test_failure_via_direct_construction(self) -> None:
        result = ValidationResult(ok=False, handler="type", error="expected int")
        assert result.error == "expected int"


class TestInvariants:
    def test_successful_result_may_not_have_error(self) -> None:
        with pytest.raises(ValueError, match="cannot carry an error"):
            ValidationResult(ok=True, handler="presence", error="oops")

    def test_failed_result_requires_error_message(self) -> None:
        with pytest.raises(ValueError, match="must carry an error message"):
            ValidationResult(ok=False, handler="presence", error=None)

    def test_failed_result_rejects_empty_error(self) -> None:
        with pytest.raises(ValueError, match="must carry an error message"):
            ValidationResult(ok=False, handler="presence", error="")

    def test_handler_name_must_not_be_empty(self) -> None:
        with pytest.raises(ValueError, match="handler name"):
            ValidationResult.success("")


class TestImmutability:
    def test_cannot_reassign_field(self) -> None:
        result = ValidationResult.success("presence")
        with pytest.raises(FrozenInstanceError):
            result.ok = False  # type: ignore[misc]

    def test_two_equal_results_compare_equal(self) -> None:
        a = ValidationResult.failure("type", "expected int")
        b = ValidationResult.failure("type", "expected int")
        assert a == b

    def test_results_are_hashable(self) -> None:
        results = {
            ValidationResult.success("presence"),
            ValidationResult.success("presence"),
            ValidationResult.failure("range", "too big"),
        }
        assert len(results) == 2
