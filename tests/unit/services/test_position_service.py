"""Unit tests for PositionService using plain fakes -- no database, no mocking library.

FillSource and SnapshotSink are Protocols, so these fakes satisfy them
structurally without inheriting from anything.
"""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument
from concord_core.services.position_service import PositionService

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _fill(execution_id: str, quantity: str) -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=AAPL,
        side=Side.BUY,
        quantity=Decimal(quantity),
        price=Decimal("100"),
        executed_at=T0,
        status=TradeStatus.NEW,
    )


class _FakeFillSource:
    def __init__(self, fills: list[Fill]) -> None:
        self._fills = fills
        self.requested_instruments: list[Instrument] = []

    async def get_by_instrument(self, instrument: Instrument) -> list[Fill]:
        self.requested_instruments.append(instrument)
        return self._fills


class _FakeSnapshotSink:
    def __init__(self) -> None:
        self.inserted: list[Position] = []

    async def insert_snapshot(self, position: Position) -> None:
        self.inserted.append(position)


async def test_compute_position_returns_none_when_instrument_never_traded() -> None:
    service = PositionService(_FakeFillSource([]), _FakeSnapshotSink())
    assert await service.compute_position(AAPL) is None


async def test_compute_position_folds_fills_via_build_position() -> None:
    fills = [_fill("EX-1", "100"), _fill("EX-2", "50")]
    service = PositionService(_FakeFillSource(fills), _FakeSnapshotSink())
    position = await service.compute_position(AAPL)
    assert position is not None
    assert position.quantity == Decimal("150")


async def test_compute_and_snapshot_persists_computed_position() -> None:
    fills = [_fill("EX-1", "100")]
    sink = _FakeSnapshotSink()
    service = PositionService(_FakeFillSource(fills), sink)
    position = await service.compute_and_snapshot(AAPL)
    assert sink.inserted == [position]


async def test_compute_and_snapshot_does_not_persist_when_no_position_exists() -> None:
    sink = _FakeSnapshotSink()
    service = PositionService(_FakeFillSource([]), sink)
    result = await service.compute_and_snapshot(AAPL)
    assert result is None
    assert sink.inserted == []
