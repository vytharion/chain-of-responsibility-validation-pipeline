from __future__ import annotations

import pytest

from validation_pipeline import (
    ChainBuilder,
    EMAIL_PATTERN,
    ExecutionMode,
    MinLengthHandler,
    PatternHandler,
    RegistrationOutcome,
    ValidationResult,
    build_registration_chain,
    register_user,
)


VALID_PAYLOAD = {
    "email": "  New.User@Example.com  ",
    "password": "correct horse battery",
    "display_name": "  Vy Nguyen  ",
    "age": 27,
}


class TestMinLengthHandler:
    def test_forwards_when_value_meets_minimum(self) -> None:
        handler = MinLengthHandler("password", 8)
        assert handler.handle({"password": "supersecret"}) is None

    def test_reports_failure_when_value_below_minimum(self) -> None:
        handler = MinLengthHandler("password", 8)
        result = handler.handle({"password": "short"})
        assert result is not None
        assert result.ok is False
        assert result.handler == "min_length[password:8]"
        assert "below minimum 8" in (result.error or "")

    def test_missing_field_is_forwarded(self) -> None:
        handler = MinLengthHandler("password", 8)
        assert handler.handle({"other": "value"}) is None

    def test_non_string_value_is_forwarded_not_failed(self) -> None:
        handler = MinLengthHandler("password", 8)
        assert handler.handle({"password": 12345}) is None

    def test_negative_minimum_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="minimum length"):
            MinLengthHandler("password", -1)

    def test_empty_field_name_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="field name"):
            MinLengthHandler("", 8)


class TestPatternHandler:
    def test_forwards_when_value_matches_pattern(self) -> None:
        handler = PatternHandler("email", EMAIL_PATTERN, "email")
        assert handler.handle({"email": "vy@example.com"}) is None

    def test_reports_failure_when_value_does_not_match(self) -> None:
        handler = PatternHandler("email", EMAIL_PATTERN, "email")
        result = handler.handle({"email": "not-an-email"})
        assert result is not None
        assert result.ok is False
        assert result.handler == "pattern[email:email]"
        assert "email" in (result.error or "")

    def test_partial_match_is_rejected_because_fullmatch_is_used(self) -> None:
        handler = PatternHandler("email", EMAIL_PATTERN, "email")
        result = handler.handle({"email": "vy@example.com trailing"})
        assert result is not None
        assert result.ok is False

    def test_missing_field_is_forwarded(self) -> None:
        handler = PatternHandler("email", EMAIL_PATTERN, "email")
        assert handler.handle({"other": "value"}) is None

    def test_non_string_value_is_forwarded(self) -> None:
        handler = PatternHandler("email", EMAIL_PATTERN, "email")
        assert handler.handle({"email": 42}) is None

    def test_accepts_precompiled_pattern(self) -> None:
        import re

        compiled = re.compile(r"[A-Z]{3}")
        handler = PatternHandler("code", compiled, "code")
        assert handler.handle({"code": "ABC"}) is None
        result = handler.handle({"code": "ab"})
        assert result is not None
        assert result.handler == "pattern[code:code]"

    def test_default_label_is_used_when_omitted(self) -> None:
        handler = PatternHandler("code", r"\d+")
        assert handler.name == "pattern[code:pattern]"


class TestRegistrationOutcome:
    def test_accept_stores_normalized_payload(self) -> None:
        outcome = RegistrationOutcome.accept({"email": "vy@example.com"})
        assert outcome.accepted is True
        assert outcome.errors == ()
        assert outcome.normalized == {"email": "vy@example.com"}

    def test_reject_stores_errors_as_tuple(self) -> None:
        err = ValidationResult.failure("presence[email]", "missing")
        outcome = RegistrationOutcome.reject([err])
        assert outcome.accepted is False
        assert outcome.errors == (err,)
        assert outcome.normalized is None

    def test_reject_without_errors_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one error"):
            RegistrationOutcome.reject([])

    def test_accepted_with_errors_raises(self) -> None:
        err = ValidationResult.failure("presence[email]", "missing")
        with pytest.raises(ValueError, match="cannot carry errors"):
            RegistrationOutcome(accepted=True, errors=(err,), normalized={})

    def test_accepted_without_normalized_raises(self) -> None:
        with pytest.raises(ValueError, match="normalized payload"):
            RegistrationOutcome(accepted=True, errors=(), normalized=None)

    def test_error_messages_extracts_strings_in_order(self) -> None:
        errors = [
            ValidationResult.failure("presence[email]", "missing email"),
            ValidationResult.failure("range[age:13..120]", "age out of range"),
        ]
        outcome = RegistrationOutcome.reject(errors)
        assert outcome.error_messages == ("missing email", "age out of range")


class TestBuildRegistrationChain:
    def test_returns_a_populated_chain_builder(self) -> None:
        chain = build_registration_chain()
        assert isinstance(chain, ChainBuilder)
        assert len(chain) == 12

    def test_each_invocation_returns_a_fresh_builder(self) -> None:
        first = build_registration_chain()
        second = build_registration_chain()
        assert first is not second
        assert first._handlers[0] is not second._handlers[0]


class TestRegisterUserHappyPath:
    def test_valid_payload_is_accepted(self) -> None:
        outcome = register_user(VALID_PAYLOAD)
        assert outcome.accepted is True
        assert outcome.errors == ()

    def test_accepted_payload_is_normalized(self) -> None:
        outcome = register_user(VALID_PAYLOAD)
        assert outcome.normalized == {
            "email": "new.user@example.com",
            "password": "correct horse battery",
            "display_name": "Vy Nguyen",
            "age": 27,
        }

    def test_normalization_leaves_untouched_fields_alone(self) -> None:
        outcome = register_user({**VALID_PAYLOAD, "age": 42})
        assert outcome.normalized is not None
        assert outcome.normalized["age"] == 42


class TestRegisterUserRejectionCollectsAll:
    def test_empty_payload_reports_every_required_field(self) -> None:
        outcome = register_user({})
        assert outcome.accepted is False
        handlers = [e.handler for e in outcome.errors]
        assert "presence[email]" in handlers
        assert "presence[password]" in handlers
        assert "presence[display_name]" in handlers
        assert "presence[age]" in handlers

    def test_multiple_independent_failures_are_all_reported(self) -> None:
        outcome = register_user(
            {
                "email": "not-an-email",
                "password": "short",
                "display_name": "V",
                "age": 5,
            }
        )
        assert outcome.accepted is False
        handlers = [e.handler for e in outcome.errors]
        assert "pattern[email:email]" in handlers
        assert "min_length[password:8]" in handlers
        assert "min_length[display_name:2]" in handlers
        assert "range[age:13..120]" in handlers

    def test_rejected_outcome_has_no_normalized_payload(self) -> None:
        outcome = register_user({})
        assert outcome.normalized is None


class TestRegisterUserShortCircuitMode:
    def test_short_circuit_returns_only_first_failure(self) -> None:
        outcome = register_user(
            {
                "email": "not-an-email",
                "password": "short",
                "display_name": "V",
                "age": 5,
            },
            mode=ExecutionMode.SHORT_CIRCUIT,
        )
        assert outcome.accepted is False
        assert len(outcome.errors) == 1
        assert outcome.errors[0].handler == "pattern[email:email]"

    def test_short_circuit_default_can_be_swapped_by_caller(self) -> None:
        # The default is COLLECT_ALL; passing SHORT_CIRCUIT explicitly
        # opts into the fast-fail behaviour.
        outcome_all = register_user({"age": "not an int"})
        outcome_first = register_user(
            {"age": "not an int"}, mode=ExecutionMode.SHORT_CIRCUIT
        )
        assert len(outcome_all.errors) > len(outcome_first.errors)


class TestRegisterUserWithCustomChain:
    def test_caller_can_supply_a_narrower_chain(self) -> None:
        custom = ChainBuilder().presence("email").type_of("email", str)
        outcome = register_user(
            {"email": "vy@example.com"}, chain=custom
        )
        assert outcome.accepted is True
        assert outcome.normalized == {"email": "vy@example.com"}

    def test_custom_chain_still_reports_failures(self) -> None:
        custom = ChainBuilder().presence("email")
        outcome = register_user({}, chain=custom)
        assert outcome.accepted is False
        assert outcome.errors[0].handler == "presence[email]"


class TestRegisterUserWiringInvariants:
    def test_registration_does_not_mutate_caller_payload(self) -> None:
        payload = dict(VALID_PAYLOAD)
        register_user(payload)
        assert payload == VALID_PAYLOAD

    def test_registration_type_failure_short_circuits_range_in_default_mode(
        self,
    ) -> None:
        # COLLECT_ALL still lets range and type both fire when the value
        # is numeric-looking but wrong type; when the value is a string
        # only the type handler fires because range forwards non-numerics.
        outcome = register_user({**VALID_PAYLOAD, "age": "twenty"})
        handlers = [e.handler for e in outcome.errors]
        assert "type[age:int]" in handlers
        assert "range[age:13..120]" not in handlers
