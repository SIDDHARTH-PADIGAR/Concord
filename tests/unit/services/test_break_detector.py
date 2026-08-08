"""Tests for BreakDetector's raise/resolve/no-op state transitions.

Uses plain fakes (BreakEventSource/Sink are Protocols) with an
injected deterministic id_factory, so break IDs are directly assertable.
"""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.enums import InstrumentType
from concord_core.domain.reconciliation import ReconciliationResult
from concord_core.domain.value_objects import Instrument
from concord_core.services.break_detector import BreakDetector

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 8, 5, 13, 0, 0, tzinfo=UTC)


def _result(is_break: bool, difference: str = "0", as_of: datetime = T0) -> ReconciliationResult:
    return ReconciliationResult(
        instrument=AAPL,
        internal_quantity=Decimal("100"),
        street_quantity=Decimal("100") + Decimal(difference),
        difference=Decimal(difference),
        is_break=is_break,
        as_of=as_of,
    )


class _FakeBreakEventSource:
    def __init__(self, latest: BreakEvent | None) -> None:
        self._latest = latest

    async def get_latest_break_event(self, instrument: Instrument) -> BreakEvent | None:
        return self._latest


class _FakeBreakEventSink:
    def __init__(self) -> None:
        self.inserted: list[BreakEvent] = []

    async def insert_break_event(self, event: BreakEvent) -> None:
        self.inserted.append(event)


def _sequential_id_factory(ids: list[str]):
    iterator = iter(ids)
    return lambda: next(iterator)


async def test_no_open_break_and_no_break_result_is_a_noop() -> None:
    source = _FakeBreakEventSource(latest=None)
    sink = _FakeBreakEventSink()
    detector = BreakDetector(source, sink)

    result = await detector.detect(AAPL, _result(is_break=False))

    assert result is None
    assert sink.inserted == []


async def test_no_open_break_and_break_result_raises_new_break() -> None:
    source = _FakeBreakEventSource(latest=None)
    sink = _FakeBreakEventSink()
    detector = BreakDetector(source, sink, id_factory=_sequential_id_factory(["BRK-1"]))

    event = await detector.detect(AAPL, _result(is_break=True, difference="10"))

    assert event is not None
    assert event.status == BreakStatus.RAISED
    assert event.break_id == "BRK-1"
    assert event.difference == Decimal("10")
    assert sink.inserted == [event]


async def test_open_break_and_still_break_result_is_a_noop() -> None:
    existing = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    source = _FakeBreakEventSource(latest=existing)
    sink = _FakeBreakEventSink()
    detector = BreakDetector(source, sink)

    result = await detector.detect(AAPL, _result(is_break=True, difference="12", as_of=T1))

    assert result is None
    assert sink.inserted == []


async def test_open_break_and_no_longer_break_result_resolves_with_same_break_id() -> None:
    existing = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    source = _FakeBreakEventSource(latest=existing)
    sink = _FakeBreakEventSink()
    detector = BreakDetector(source, sink)

    event = await detector.detect(AAPL, _result(is_break=False, as_of=T1))

    assert event is not None
    assert event.status == BreakStatus.RESOLVED
    assert event.break_id == "BRK-1"
    assert event.detected_at == T1
    assert sink.inserted == [event]


async def test_resolved_break_and_new_break_result_raises_a_new_break_id() -> None:
    resolved = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RESOLVED,
        difference=Decimal("0"),
        detected_at=T0,
    )
    source = _FakeBreakEventSource(latest=resolved)
    sink = _FakeBreakEventSink()
    detector = BreakDetector(source, sink, id_factory=_sequential_id_factory(["BRK-2"]))

    event = await detector.detect(AAPL, _result(is_break=True, difference="5", as_of=T1))

    assert event is not None
    assert event.status == BreakStatus.RAISED
    assert event.break_id == "BRK-2"
