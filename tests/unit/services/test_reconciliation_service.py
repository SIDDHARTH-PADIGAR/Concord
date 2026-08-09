"""Tests for ReconciliationService orchestration.

Uses real ReconciliationEngine and real BreakDetector as collaborators
(both already independently unit-tested) -- only the storage-boundary
Protocols (InternalPositionSource, StreetPositionSource, BreakEventSource/
Sink) are faked. This tests the wiring, not logic already covered elsewhere.
"""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument
from concord_core.services.break_detector import BreakDetector
from concord_core.services.reconciliation_engine import ReconciliationEngine
from concord_core.services.reconciliation_service import ReconciliationService

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _position(quantity: str) -> Position:
    return Position(instrument=AAPL, quantity=Decimal(quantity), as_of=T0)


class _FakeInternalPositionSource:
    def __init__(self, position: Position | None) -> None:
        self._position = position

    async def compute_position(self, instrument: Instrument) -> Position | None:
        return self._position


class _FakeStreetPositionSource:
    def __init__(self, position: Position | None) -> None:
        self._position = position

    async def get_position(self, instrument: Instrument) -> Position | None:
        return self._position


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


def _build_service(
    internal: Position | None,
    street: Position | None,
    existing_break: BreakEvent | None = None,
    tolerance: Decimal = Decimal("0"),
    clock_value: datetime = T0,
) -> tuple[ReconciliationService, _FakeBreakEventSink]:
    sink = _FakeBreakEventSink()
    service = ReconciliationService(
        internal_source=_FakeInternalPositionSource(internal),
        street_source=_FakeStreetPositionSource(street),
        engine=ReconciliationEngine(tolerance=tolerance),
        break_detector=BreakDetector(
            _FakeBreakEventSource(existing_break), sink, id_factory=lambda: "BRK-1"
        ),
        clock=lambda: clock_value,
    )
    return service, sink


async def test_matching_positions_raises_no_break() -> None:
    service, sink = _build_service(internal=_position("100"), street=_position("100"))

    result = await service.reconcile_instrument(AAPL)

    assert result is None
    assert sink.inserted == []


async def test_mismatched_positions_raises_a_break() -> None:
    service, sink = _build_service(internal=_position("100"), street=_position("90"))

    result = await service.reconcile_instrument(AAPL)

    assert result is not None
    assert result.status == BreakStatus.RAISED
    assert result.break_id == "BRK-1"
    assert sink.inserted == [result]


async def test_already_broken_and_still_mismatched_is_a_noop() -> None:
    existing = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    service, sink = _build_service(
        internal=_position("100"), street=_position("90"), existing_break=existing
    )

    result = await service.reconcile_instrument(AAPL)

    assert result is None
    assert sink.inserted == []


async def test_open_break_that_now_matches_resolves() -> None:
    existing = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    service, _sink = _build_service(
        internal=_position("100"), street=_position("100"), existing_break=existing
    )

    result = await service.reconcile_instrument(AAPL)

    assert result is not None
    assert result.status == BreakStatus.RESOLVED
    assert result.break_id == "BRK-1"


async def test_uses_injected_clock_for_as_of() -> None:
    custom_time = datetime(2026, 8, 5, 15, 30, 0, tzinfo=UTC)
    service, _ = _build_service(
        internal=_position("100"), street=_position("90"), clock_value=custom_time
    )

    result = await service.reconcile_instrument(AAPL)

    assert result is not None
    assert result.detected_at == custom_time


async def test_neither_side_has_a_position_raises_no_break() -> None:
    service, sink = _build_service(internal=None, street=None)

    result = await service.reconcile_instrument(AAPL)

    assert result is None
    assert sink.inserted == []


async def test_missing_internal_position_with_real_street_position_raises_a_break() -> None:
    service, sink = _build_service(internal=None, street=_position("100"))

    result = await service.reconcile_instrument(AAPL)

    assert result is not None
    assert result.status == BreakStatus.RAISED
    assert sink.inserted == [result]
