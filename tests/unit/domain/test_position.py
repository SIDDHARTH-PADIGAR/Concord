"""Tests for Position and build_position (Fill -> Position aggregation).

These protect the core reconciliation-relevant business logic: how a
fill history -- including corrections and cancellations -- folds into
a net position. Getting this wrong doesn't crash anything; it produces
a plausible-looking but incorrect position that would silently corrupt
every downstream reconciliation result.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.position import Position, build_position
from concord_core.domain.value_objects import Instrument

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
MSFT = Instrument(symbol="MSFT", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _fill(
    execution_id: str,
    side: Side,
    quantity: str,
    executed_at: datetime = T0,
    instrument: Instrument = AAPL,
    status: TradeStatus = TradeStatus.NEW,
    corrects_execution_id: str | None = None,
) -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=instrument,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal("100"),
        executed_at=executed_at,
        status=status,
        corrects_execution_id=corrects_execution_id,
    )


class TestBuildPosition:
    def test_empty_fills_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            build_position([])

    def test_single_buy_fill(self) -> None:
        position = build_position([_fill("EX-1", Side.BUY, "100")])
        assert position.quantity == Decimal("100")
        assert position.instrument == AAPL

    def test_multiple_new_fills_net_correctly(self) -> None:
        fills = [
            _fill("EX-1", Side.BUY, "100"),
            _fill("EX-2", Side.SELL, "40"),
            _fill("EX-3", Side.BUY, "10"),
        ]
        position = build_position(fills)
        assert position.quantity == Decimal("70")

    def test_mixed_instruments_raises(self) -> None:
        fills = [_fill("EX-1", Side.BUY, "100"), _fill("EX-2", Side.BUY, "50", instrument=MSFT)]
        with pytest.raises(ValueError, match="same instrument"):
            build_position(fills)

    def test_corrected_fill_replaces_original_quantity(self) -> None:
        fills = [
            _fill("EX-1", Side.BUY, "100"),
            _fill(
                "EX-2",
                Side.BUY,
                "80",
                status=TradeStatus.CORRECTED,
                corrects_execution_id="EX-1",
                executed_at=T0 + timedelta(minutes=1),
            ),
        ]
        position = build_position(fills)
        assert position.quantity == Decimal("80")

    def test_cancelled_fill_removes_original_entirely(self) -> None:
        fills = [
            _fill("EX-1", Side.BUY, "100"),
            _fill("EX-2", Side.BUY, "50"),
            _fill(
                "EX-3",
                Side.BUY,
                "100",
                status=TradeStatus.CANCELLED,
                corrects_execution_id="EX-1",
                executed_at=T0 + timedelta(minutes=1),
            ),
        ]
        position = build_position(fills)
        assert position.quantity == Decimal("50")

    def test_correction_referencing_missing_original_raises(self) -> None:
        fills = [
            _fill(
                "EX-2",
                Side.BUY,
                "80",
                status=TradeStatus.CORRECTED,
                corrects_execution_id="EX-1",
            )
        ]
        with pytest.raises(ValueError, match="not present in the supplied fill set"):
            build_position(fills)

    def test_as_of_reflects_latest_event_including_cancellation(self) -> None:
        fills = [
            _fill("EX-1", Side.BUY, "100"),
            _fill(
                "EX-2",
                Side.BUY,
                "100",
                status=TradeStatus.CANCELLED,
                corrects_execution_id="EX-1",
                executed_at=T0 + timedelta(hours=1),
            ),
        ]
        position = build_position(fills)
        assert position.as_of == T0 + timedelta(hours=1)

    def test_fully_cancelled_position_nets_to_zero(self) -> None:
        fills = [
            _fill("EX-1", Side.BUY, "100"),
            _fill(
                "EX-2",
                Side.BUY,
                "100",
                status=TradeStatus.CANCELLED,
                corrects_execution_id="EX-1",
                executed_at=T0 + timedelta(minutes=1),
            ),
        ]
        position = build_position(fills)
        assert position.quantity == Decimal("0")


class TestPosition:
    def test_position_is_frozen(self) -> None:
        position = Position(instrument=AAPL, quantity=Decimal("100"), as_of=T0)
        with pytest.raises(ValidationError):
            position.quantity = Decimal("200")

    def test_naive_as_of_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Position(instrument=AAPL, quantity=Decimal("100"), as_of=datetime(2026, 8, 5))
