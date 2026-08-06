"""Tests for Fill <-> Redis Stream field serialization."""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.messaging.serialization import fill_from_stream_fields, fill_to_stream_fields


def _sample_fill() -> Fill:
    return Fill(
        exchange_execution_id="EX-1",
        trade_id="TR-1",
        instrument=Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY),
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150.25"),
        executed_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC),
        status=TradeStatus.NEW,
    )


def test_round_trip_preserves_fill() -> None:
    fill = _sample_fill()
    fields = fill_to_stream_fields(fill)
    assert fill_from_stream_fields(fields) == fill


def test_fields_are_flat_strings() -> None:
    """Redis Stream fields must be str -> str; a nested dict would break XADD."""
    fields = fill_to_stream_fields(_sample_fill())
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in fields.items())
