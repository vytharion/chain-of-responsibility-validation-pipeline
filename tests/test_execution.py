from __future__ import annotations

import pytest

from validation_pipeline import (
    ChainBuilder,
    ExecutionMode,
    ValidationResult,
)


class TestExecutionModeEnum:
    def test_two_modes_exist(self) -> None:
        assert ExecutionMode.SHORT_CIRCUIT is not ExecutionMode.COLLECT_ALL

    def test_modes_have_stable_string_values(self) -> None:
        assert ExecutionMode.SHORT_CIRCUIT.value == "short_circuit"
        assert ExecutionMode.COLLECT_ALL.value == "collect_all"


class TestRunAllHappyPath:
    def test_run_all_returns_empty_list_when_every_handler_passes(self) -> None:
        failures = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .range_of("age", 0, 120)
            .run_all({"age": 30})
        )
        assert failures == []

    def test_run_all_on_empty_builder_raises(self) -> None:
        with pytest.raises(ValueError, match="empty chain"):
            ChainBuilder().run_all({"any": "payload"})


class TestRunAllCollectsEveryFailure:
    def test_run_all_reports_both_presence_and_range_failures(self) -> None:
        failures = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
            .run_all({"score": 999})
        )
        assert len(failures) == 2
        assert failures[0].handler == "presence[age]"
        assert failures[1].handler == "range[score:0..100]"

    def test_run_all_preserves_handler_insertion_order(self) -> None:
        failures = (
            ChainBuilder()
            .presence("email")
            .presence("name")
            .presence("phone")
            .run_all({})
        )
        assert [f.handler for f in failures] == [
            "presence[email]",
            "presence[name]",
            "presence[phone]",
        ]

    def test_run_all_reports_every_failure_all_from_the_same_field(self) -> None:
        # A float that is also out of range fires both handlers because
        # collect-all runs each validator independently against the payload.
        failures = (
            ChainBuilder()
            .type_of("age", int)
            .range_of("age", 0, 120)
            .run_all({"age": 999.5})
        )
        assert [f.handler for f in failures] == [
            "type[age:int]",
            "range[age:0..120]",
        ]

    def test_run_all_returns_only_failures_not_successes(self) -> None:
        failures = (
            ChainBuilder()
            .presence("email")  # will pass
            .presence("missing")  # will fail
            .run_all({"email": "vy@example.com"})
        )
        assert len(failures) == 1
        assert failures[0].handler == "presence[missing]"
        assert failures[0].ok is False


class TestRunAllDoesNotShortCircuit:
    def test_first_failure_does_not_stop_downstream_handlers(self) -> None:
        # Even though presence fails first, range must still be executed.
        failures = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
            .run_all({"score": -5})
        )
        handlers = [f.handler for f in failures]
        assert "presence[age]" in handlers
        assert "range[score:0..100]" in handlers

    def test_short_circuit_reports_only_first_failure_by_contrast(self) -> None:
        outcome = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
            .run({"score": -5})
        )
        assert outcome is not None
        assert outcome.handler == "presence[age]"


class TestExecuteDispatcher:
    def test_execute_short_circuit_mode_returns_first_failure_wrapped_in_list(
        self,
    ) -> None:
        results = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
            .execute({"score": -5}, mode=ExecutionMode.SHORT_CIRCUIT)
        )
        assert len(results) == 1
        assert results[0].handler == "presence[age]"

    def test_execute_short_circuit_returns_empty_list_when_all_pass(self) -> None:
        results = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .execute({"age": 30}, mode=ExecutionMode.SHORT_CIRCUIT)
        )
        assert results == []

    def test_execute_collect_all_matches_run_all(self) -> None:
        builder = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
        )
        collected = builder.execute({"score": -5}, mode=ExecutionMode.COLLECT_ALL)
        direct = ChainBuilder().presence("age").range_of("score", 0, 100).run_all(
            {"score": -5}
        )
        assert [r.handler for r in collected] == [r.handler for r in direct]

    def test_execute_defaults_to_short_circuit(self) -> None:
        results = (
            ChainBuilder()
            .presence("age")
            .range_of("score", 0, 100)
            .execute({"score": -5})
        )
        assert len(results) == 1
        assert results[0].handler == "presence[age]"


class TestRunAllIsolatesHandlerLinks:
    def test_run_all_resets_stale_next_links_so_handlers_run_independently(
        self,
    ) -> None:
        builder = ChainBuilder().presence("age").presence("name")
        # Poison the wiring so a bug in reset would surface here.
        first, second = builder._handlers
        first.set_next(second)
        second.set_next(first)  # cycle!

        failures = builder.run_all({})

        # If the reset works, every handler runs exactly once and produces
        # exactly one verdict for the missing field it guards.
        assert [f.handler for f in failures] == [
            "presence[age]",
            "presence[name]",
        ]

    def test_run_all_returns_ValidationResult_instances(self) -> None:
        failures = ChainBuilder().presence("age").run_all({})
        assert all(isinstance(f, ValidationResult) for f in failures)
