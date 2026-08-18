from __future__ import annotations

from typing import Any, Optional

import pytest

from validation_pipeline import (
    ChainBuilder,
    Handler,
    PresenceHandler,
    RangeHandler,
    TypeHandler,
    ValidationResult,
)


class RecordingHandler(Handler):
    def __init__(self, name: str, verdict: Optional[ValidationResult] = None) -> None:
        super().__init__()
        self.name = name
        self.verdict = verdict
        self.seen: list[Any] = []

    def handle(self, payload: Any) -> Optional[ValidationResult]:
        self.seen.append(payload)
        if self.verdict is not None:
            return self.verdict
        return self._forward(payload)


class TestFluentAdd:
    def test_add_returns_the_builder_for_chaining(self) -> None:
        builder = ChainBuilder()
        returned = builder.add(RecordingHandler("first"))
        assert returned is builder

    def test_add_accumulates_handlers_in_insertion_order(self) -> None:
        a = RecordingHandler("a")
        b = RecordingHandler("b")
        c = RecordingHandler("c")
        builder = ChainBuilder().add(a).add(b).add(c)
        assert len(builder) == 3

    def test_add_rejects_non_handler_objects(self) -> None:
        builder = ChainBuilder()
        with pytest.raises(TypeError, match="Handler instance"):
            builder.add("not a handler")  # type: ignore[arg-type]

    def test_add_rejects_duplicate_handler_instance(self) -> None:
        handler = RecordingHandler("solo")
        builder = ChainBuilder().add(handler)
        with pytest.raises(ValueError, match="cannot be added twice"):
            builder.add(handler)


class TestBuild:
    def test_build_empty_chain_raises(self) -> None:
        with pytest.raises(ValueError, match="empty chain"):
            ChainBuilder().build()

    def test_build_returns_the_first_handler_as_head(self) -> None:
        first = RecordingHandler("first")
        second = RecordingHandler("second")
        head = ChainBuilder().add(first).add(second).build()
        assert head is first

    def test_build_links_handlers_in_insertion_order(self) -> None:
        a = RecordingHandler("a")
        b = RecordingHandler("b")
        c = RecordingHandler("c")
        ChainBuilder().add(a).add(b).add(c).build()
        assert a.next_handler is b
        assert b.next_handler is c
        assert c.next_handler is None

    def test_build_forwards_payload_through_every_handler(self) -> None:
        a = RecordingHandler("a")
        b = RecordingHandler("b")
        c = RecordingHandler("c")
        head = ChainBuilder().add(a).add(b).add(c).build()

        outcome = head.handle({"any": "payload"})

        assert outcome is None
        assert a.seen == [{"any": "payload"}]
        assert b.seen == [{"any": "payload"}]
        assert c.seen == [{"any": "payload"}]

    def test_build_short_circuits_on_first_verdict(self) -> None:
        verdict = ValidationResult.failure("middle", "boom")
        first = RecordingHandler("first")
        middle = RecordingHandler("middle", verdict=verdict)
        last = RecordingHandler("last")
        head = ChainBuilder().add(first).add(middle).add(last).build()

        outcome = head.handle("payload")

        assert outcome is verdict
        assert last.seen == []

    def test_build_is_idempotent_and_resets_stale_links(self) -> None:
        first = RecordingHandler("first")
        second = RecordingHandler("second")
        third = RecordingHandler("third")
        first.set_next(third)  # pre-existing stale wiring

        head = ChainBuilder().add(first).add(second).build()

        assert head is first
        assert first.next_handler is second
        assert second.next_handler is None
        assert third.next_handler is None


class TestSingleHandlerChain:
    def test_single_handler_chain_leaves_tail_unlinked(self) -> None:
        solo = RecordingHandler("solo")
        head = ChainBuilder().add(solo).build()
        assert head is solo
        assert solo.next_handler is None

    def test_single_handler_chain_still_runs(self) -> None:
        solo = RecordingHandler("solo")
        head = ChainBuilder().add(solo).build()
        assert head.handle({"any": "payload"}) is None
        assert solo.seen == [{"any": "payload"}]


class TestConvenienceFactoryMethods:
    def test_presence_shortcut_wires_a_presence_handler(self) -> None:
        builder = ChainBuilder().presence("email")
        head = builder.build()
        assert isinstance(head, PresenceHandler)
        result = head.handle({})
        assert result is not None
        assert result.ok is False
        assert result.handler == "presence[email]"

    def test_type_of_shortcut_wires_a_type_handler(self) -> None:
        builder = ChainBuilder().type_of("age", int)
        head = builder.build()
        assert isinstance(head, TypeHandler)
        result = head.handle({"age": "old"})
        assert result is not None
        assert result.handler == "type[age:int]"

    def test_range_of_shortcut_wires_a_range_handler(self) -> None:
        builder = ChainBuilder().range_of("age", 0, 120)
        head = builder.build()
        assert isinstance(head, RangeHandler)
        result = head.handle({"age": 999})
        assert result is not None
        assert result.handler == "range[age:0..120]"

    def test_fluent_composition_of_all_three_shortcuts(self) -> None:
        builder = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .range_of("age", 0, 120)
        )
        head = builder.build()

        assert head.handle({"age": 30}) is None

        result = head.handle({"age": 999})
        assert result is not None
        assert result.handler == "range[age:0..120]"


class TestRunShortcut:
    def test_run_returns_none_when_the_chain_passes(self) -> None:
        outcome = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .range_of("age", 0, 120)
            .run({"age": 30})
        )
        assert outcome is None

    def test_run_returns_first_verdict_on_failure(self) -> None:
        outcome = (
            ChainBuilder()
            .presence("age")
            .type_of("age", int)
            .range_of("age", 0, 120)
            .run({"age": "old"})
        )
        assert outcome is not None
        assert outcome.ok is False
        assert outcome.handler == "type[age:int]"

    def test_run_on_empty_builder_raises(self) -> None:
        with pytest.raises(ValueError, match="empty chain"):
            ChainBuilder().run({"any": "payload"})
