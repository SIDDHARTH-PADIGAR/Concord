"""Tests for ReconciliationResult."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from concord_core.domain.enums import InstrumentType
from concord_core.domain.reconciliation import ReconciliationResult
from concord_core.domain.value_objects import Instrument

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def test_valid_result_constructs() -> None:
    result = ReconciliationResult(
        instrument=AAPL,
        internal_quantity=Decimal("100"),
        street_quantity=Decimal("100"),
        difference=Decimal("0"),
        is_break=False,
        as_of=T0,
    )
    assert result.is_break is False


def test_result_is_frozen() -> None:
    result = ReconciliationResult(
        instrument=AAPL,
        internal_quantity=Decimal("100"),
        street_quantity=Decimal("100"),
        difference=Decimal("0"),
        is_break=False,
        as_of=T0,
    )
    with pytest.raises(ValidationError):
        result.is_break = True


def test_naive_as_of_rejected() -> None:
    with pytest.raises(ValidationError):
        ReconciliationResult(
            instrument=AAPL,
            internal_quantity=Decimal("100"),
            street_quantity=Decimal("100"),
            difference=Decimal("0"),
            is_break=False,
            as_of=datetime(2026, 8, 5, 12, 0, 0),
        )


def test_missing_side_quantities_are_none() -> None:
    result = ReconciliationResult(
        instrument=AAPL,
        internal_quantity=None,
        street_quantity=Decimal("50"),
        difference=Decimal("50"),
        is_break=True,
        as_of=T0,
    )
    assert result.internal_quantity is None
