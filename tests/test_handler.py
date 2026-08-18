from __future__ import annotations

from typing import Any, Optional

import pytest

from validation_pipeline import Handler, ValidationResult


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


class TestAbstractContract:
    def test_cannot_instantiate_bare_handler(self) -> None:
        with pytest.raises(TypeError):
            Handler()  # type: ignore[abstract]

    def test_subclass_missing_handle_is_still_abstract(self) -> None:
        class Incomplete(Handler):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


class TestSetNext:
    def test_set_next_returns_the_next_handler_for_chaining(self) -> None:
        first = RecordingHandler("first")
        second = RecordingHandler("second")
        returned = first.set_next(second)
        assert returned is second
        assert first.next_handler is second

    def test_new_handler_has_no_next_by_default(self) -> None:
        handler = RecordingHandler("solo")
        assert handler.next_handler is None

    def test_set_next_supports_fluent_chaining(self) -> None:
        a = RecordingHandler("a")
        b = RecordingHandler("b")
        c = RecordingHandler("c")
        a.set_next(b).set_next(c)
        assert a.next_handler is b
        assert b.next_handler is c
        assert c.next_handler is None

    def test_handler_may_not_point_to_itself(self) -> None:
        handler = RecordingHandler("loop")
        with pytest.raises(ValueError, match="cannot point to itself"):
            handler.set_next(handler)


class TestForwarding:
    def test_tail_handler_returning_none_bubbles_none(self) -> None:
        tail = RecordingHandler("tail")
        assert tail.handle({"any": "payload"}) is None
        assert tail.seen == [{"any": "payload"}]

    def test_forward_visits_every_handler_when_all_pass(self) -> None:
        first = RecordingHandler("first")
        second = RecordingHandler("second")
        third = RecordingHandler("third")
        first.set_next(second).set_next(third)

        outcome = first.handle("payload")

        assert outcome is None
        assert first.seen == ["payload"]
        assert second.seen == ["payload"]
        assert third.seen == ["payload"]

    def test_forward_stops_at_first_handler_that_returns_a_verdict(self) -> None:
        verdict = ValidationResult.failure("second", "boom")
        first = RecordingHandler("first")
        second = RecordingHandler("second", verdict=verdict)
        third = RecordingHandler("third")
        first.set_next(second).set_next(third)

        outcome = first.handle("payload")

        assert outcome is verdict
        assert first.seen == ["payload"]
        assert second.seen == ["payload"]
        assert third.seen == []
