"""Tests for Trade and Fill entities.

These protect the invariants that matter for correctness: immutability,
UTC-only timestamps, positive quantity/price, and the status <->
corrects_execution_id relationship that lets us tell a duplicate
delivery apart from a legitimate correction.
"""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from concord_core.domain.entities import Fill, Trade
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument

INSTRUMENT = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
UTC_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _new_fill(**overrides: object) -> Fill:
    defaults: dict[str, object] = {
        "exchange_execution_id": "EX-1",
        "trade_id": "TR-1",
        "instrument": INSTRUMENT,
        "side": Side.BUY,
        "quantity": Decimal("100"),
        "price": Decimal("150.25"),
        "executed_at": UTC_NOW,
        "status": TradeStatus.NEW,
    }
    defaults.update(overrides)
    return Fill(**defaults)  # type: ignore[arg-type]


class TestTrade:
    def test_valid_trade_constructs(self) -> None:
        trade = Trade(trade_id="TR-1", instrument=INSTRUMENT, side=Side.BUY, created_at=UTC_NOW)
        assert trade.trade_id == "TR-1"

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Trade(
                trade_id="TR-1",
                instrument=INSTRUMENT,
                side=Side.BUY,
                created_at=datetime(2026, 8, 5, 12, 0, 0),
            )

    def test_non_utc_datetime_rejected(self) -> None:
        non_utc = UTC_NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
        with pytest.raises(ValidationError):
            Trade(trade_id="TR-1", instrument=INSTRUMENT, side=Side.BUY, created_at=non_utc)

    def test_trade_is_frozen(self) -> None:
        trade = Trade(trade_id="TR-1", instrument=INSTRUMENT, side=Side.BUY, created_at=UTC_NOW)
        with pytest.raises(ValidationError):
            trade.trade_id = "TR-2"


class TestFill:
    def test_valid_new_fill_constructs(self) -> None:
        fill = _new_fill()
        assert fill.status == TradeStatus.NEW
        assert fill.corrects_execution_id is None

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _new_fill(quantity=Decimal("0"))

    def test_negative_price_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _new_fill(price=Decimal("-1"))

    def test_naive_executed_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _new_fill(executed_at=datetime(2026, 8, 5, 12, 0, 0))

    def test_new_fill_with_corrects_execution_id_rejected(self) -> None:
        """A NEW fill claiming to correct something is a contradiction, not a valid event."""
        with pytest.raises(ValidationError):
            _new_fill(corrects_execution_id="EX-0")

    def test_cancelled_fill_without_corrects_execution_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _new_fill(status=TradeStatus.CANCELLED)

    def test_corrected_fill_referencing_original_is_valid(self) -> None:
        fill = _new_fill(
            exchange_execution_id="EX-2",
            status=TradeStatus.CORRECTED,
            corrects_execution_id="EX-1",
        )
        assert fill.corrects_execution_id == "EX-1"

    def test_fill_cannot_correct_itself(self) -> None:
        with pytest.raises(ValidationError):
            _new_fill(status=TradeStatus.CORRECTED, corrects_execution_id="EX-1")

    def test_fill_is_frozen(self) -> None:
        fill = _new_fill()
        with pytest.raises(ValidationError):
            fill.quantity = Decimal("200")
