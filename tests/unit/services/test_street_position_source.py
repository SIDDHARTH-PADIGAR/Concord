"""Unit tests for StreetPositionSourceAdapter using a plain fake -- no database."""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.services.street_position_source import StreetPositionSourceAdapter

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


class _FakeStreetFillSource:
    def __init__(self, fills: list[Fill]) -> None:
        self._fills = fills

    async def get_by_instrument(self, instrument: Instrument) -> list[Fill]:
        return self._fills


async def test_get_position_returns_none_when_no_fills() -> None:
    adapter = StreetPositionSourceAdapter(_FakeStreetFillSource([]))
    assert await adapter.get_position(AAPL) is None


async def test_get_position_folds_fills_via_build_position() -> None:
    fills = [_fill("EX-1", "100"), _fill("EX-2", "50")]
    adapter = StreetPositionSourceAdapter(_FakeStreetFillSource(fills))
    position = await adapter.get_position(AAPL)
    assert position is not None
    assert position.quantity == Decimal("150")
