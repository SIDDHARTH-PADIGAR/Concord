"""Tests for BreakEvent."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def test_valid_break_event_constructs() -> None:
    event = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    assert event.status == BreakStatus.RAISED


def test_break_event_is_frozen() -> None:
    event = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    with pytest.raises(ValidationError):
        event.status = BreakStatus.RESOLVED


def test_naive_detected_at_rejected() -> None:
    with pytest.raises(ValidationError):
        BreakEvent(
            break_id="BRK-1",
            instrument=AAPL,
            status=BreakStatus.RAISED,
            difference=Decimal("10"),
            detected_at=datetime(2026, 8, 5, 12, 0, 0),
        )
