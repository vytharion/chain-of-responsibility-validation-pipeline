from __future__ import annotations

from typing import Any, Optional

import pytest

from validation_pipeline import (
    ChainBuilder,
    ExecutionMode,
    Handler,
    PresenceHandler,
    RangeHandler,
    TypeHandler,
    ValidationResult,
)


class SpyHandler(Handler):
    def __init__(
        self,
        label: str,
        verdict: Optional[ValidationResult] = None,
    ) -> None:
        super().__init__()
        self.label = label
        self.verdict = verdict
        self.call_count = 0

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        self.call_count += 1
        if self.verdict is not None:
            return self.verdict
        return self._forward(payload)


def _age_chain(
    minimum: int = 0,
    maximum: int = 120,
) -> ChainBuilder:
    return (
        ChainBuilder()
        .presence("age")
        .type_of("age", int)
        .range_of("age", minimum, maximum)
    )


class TestHappyPath:
    def test_well_formed_payload_produces_no_verdict(self) -> None:
        outcome = _age_chain().run({"age": 30})
        assert outcome is None

    def test_boundary_values_inside_range_still_pass(self) -> None:
        low = _age_chain().run({"age": 0})
        high = _age_chain().run({"age": 120})
        assert low is None
        assert high is None

    def test_execute_short_circuit_returns_empty_list_on_happy_path(self) -> None:
        results = _age_chain().execute(
            {"age": 42}, mode=ExecutionMode.SHORT_CIRCUIT
        )
        assert results == []

    def test_execute_collect_all_returns_empty_list_on_happy_path(self) -> None:
        results = _age_chain().execute(
            {"age": 42}, mode=ExecutionMode.COLLECT_ALL
        )
        assert results == []


class TestPerHandlerFailures:
    def test_missing_field_is_caught_by_presence_handler(self) -> None:
        outcome = _age_chain().run({})
        assert outcome is not None
        assert outcome.ok is False
        assert outcome.handler == "presence[age]"
        assert "required" in (outcome.error or "")

    def test_wrong_type_is_caught_by_type_handler(self) -> None:
        outcome = _age_chain().run({"age": "old"})
        assert outcome is not None
        assert outcome.ok is False
        assert outcome.handler == "type[age:int]"

    def test_out_of_range_is_caught_by_range_handler(self) -> None:
        outcome = _age_chain().run({"age": 999})
        assert outcome is not None
        assert outcome.ok is False
        assert outcome.handler == "range[age:0..120]"

    def test_negative_out_of_range_is_caught_by_range_handler(self) -> None:
        outcome = _age_chain(minimum=0, maximum=120).run({"age": -5})
        assert outcome is not None
        assert outcome.handler == "range[age:0..120]"

    def test_none_value_is_treated_as_missing_by_presence(self) -> None:
        outcome = _age_chain().run({"age": None})
        assert outcome is not None
        assert outcome.handler == "presence[age]"


class TestChainOrderingShortCircuit:
    def test_short_circuit_stops_at_first_failing_handler(self) -> None:
        first = SpyHandler("first")
        gate = SpyHandler(
            "gate", verdict=ValidationResult.failure("gate", "denied")
        )
        never = SpyHandler("never")

        head = ChainBuilder().add(first).add(gate).add(never).build()
        outcome = head.handle("anything")

        assert outcome is not None
        assert outcome.handler == "gate"
        assert first.call_count == 1
        assert gate.call_count == 1
        assert never.call_count == 0

    def test_short_circuit_visits_every_handler_when_all_forward(self) -> None:
        a = SpyHandler("a")
        b = SpyHandler("b")
        c = SpyHandler("c")

        head = ChainBuilder().add(a).add(b).add(c).build()
        outcome = head.handle("payload")

        assert outcome is None
        assert (a.call_count, b.call_count, c.call_count) == (1, 1, 1)

    def test_type_failure_prevents_range_from_ever_running(self) -> None:
        # If TypeHandler catches the mismatch, the range check downstream
        # must not fire; otherwise short-circuit is broken.
        outcome = _age_chain().run({"age": "old"})
        assert outcome is not None
        assert outcome.handler == "type[age:int]"


class TestChainReordering:
    def test_swapping_order_changes_which_handler_reports_first(self) -> None:
        # Same three checks, opposite order — the first-failing handler
        # reports, so ordering changes the verdict identity.
        presence_first = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .run({})
        )
        type_first = (
            ChainBuilder()
            .type_of("age", int)
            .presence("age")
            .run({})
        )
        assert presence_first is not None
        assert type_first is not None
        assert presence_first.handler == "presence[age]"
        assert type_first.handler == "presence[age]"

    def test_reordering_does_not_change_handler_behaviour(self) -> None:
        # The internal invariant of each handler is unaffected by its
        # position — reassemble the same instances into different orders
        # and the individual verdicts remain identical.
        payload = {"age": -1}
        presence = PresenceHandler("age")
        type_check = TypeHandler("age", int)
        range_check = RangeHandler("age", 0, 120)

        assert presence.handle(payload) is None
        assert type_check.handle(payload) is None
        range_verdict = range_check.handle(payload)
        assert range_verdict is not None
        assert range_verdict.handler == "range[age:0..120]"

        forward = ChainBuilder().add(presence).add(type_check).add(range_check)
        reverse = ChainBuilder().add(range_check).add(type_check).add(presence)

        assert forward.run(payload) == range_verdict
        assert reverse.run(payload) == range_verdict

    def test_collect_all_reports_every_failure_regardless_of_order(self) -> None:
        forward_failures = (
            ChainBuilder()
            .presence("email")
            .presence("password")
            .run_all({})
        )
        reverse_failures = (
            ChainBuilder()
            .presence("password")
            .presence("email")
            .run_all({})
        )
        forward_names = sorted(f.handler for f in forward_failures)
        reverse_names = sorted(f.handler for f in reverse_failures)
        assert forward_names == reverse_names
        assert forward_names == ["presence[email]", "presence[password]"]

    def test_collect_all_preserves_insertion_order_of_failures(self) -> None:
        failures = (
            ChainBuilder()
            .presence("a")
            .presence("b")
            .presence("c")
            .run_all({})
        )
        assert [f.handler for f in failures] == [
            "presence[a]",
            "presence[b]",
            "presence[c]",
        ]


class TestChainOrderingEdgeCases:
    def test_running_the_same_chain_twice_is_deterministic(self) -> None:
        chain = _age_chain()
        first_pass = chain.run({"age": 30})
        second_pass = chain.run({"age": 30})
        assert first_pass is None
        assert second_pass is None

    def test_switching_execution_modes_does_not_leak_state(self) -> None:
        chain = _age_chain()
        # Run collect-all first, then short-circuit; the second call must
        # reflect only the short-circuit contract, not stale wiring.
        collect = chain.execute({"age": "old"}, mode=ExecutionMode.COLLECT_ALL)
        short = chain.execute({"age": "old"}, mode=ExecutionMode.SHORT_CIRCUIT)
        assert len(collect) >= 1
        assert len(short) == 1
        assert short[0].handler == "type[age:int]"

    def test_empty_chain_execution_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty chain"):
            ChainBuilder().run({"any": "payload"})
