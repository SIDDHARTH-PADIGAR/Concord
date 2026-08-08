"""Tests for ReconciliationEngine: pure comparison logic, no I/O.

Covers the material design decisions: tolerance boundary behavior,
missing-side handling (None vs a real zero position), and the
instrument-mismatch guard.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument
from concord_core.services.reconciliation_engine import ReconciliationEngine

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
MSFT = Instrument(symbol="MSFT", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _position(quantity: str, instrument: Instrument = AAPL) -> Position:
    return Position(instrument=instrument, quantity=Decimal(quantity), as_of=T0)


class TestReconcile:
    def test_matching_positions_produce_no_break(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, _position("100"), _position("100"), as_of=T0)
        assert result.is_break is False
        assert result.difference == Decimal("0")

    def test_mismatched_positions_produce_a_break(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, _position("100"), _position("90"), as_of=T0)
        assert result.is_break is True
        assert result.difference == Decimal("-10")

    def test_difference_direction_is_street_minus_internal(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, _position("90"), _position("100"), as_of=T0)
        assert result.difference == Decimal("10")

    def test_difference_within_tolerance_is_not_a_break(self) -> None:
        engine = ReconciliationEngine(tolerance=Decimal("5"))
        result = engine.reconcile(AAPL, _position("100"), _position("103"), as_of=T0)
        assert result.is_break is False

    def test_difference_exactly_at_tolerance_is_not_a_break(self) -> None:
        engine = ReconciliationEngine(tolerance=Decimal("5"))
        result = engine.reconcile(AAPL, _position("100"), _position("105"), as_of=T0)
        assert result.is_break is False

    def test_difference_just_beyond_tolerance_is_a_break(self) -> None:
        engine = ReconciliationEngine(tolerance=Decimal("5"))
        result = engine.reconcile(AAPL, _position("100"), _position("105.01"), as_of=T0)
        assert result.is_break is True

    def test_negative_tolerance_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="not be negative"):
            ReconciliationEngine(tolerance=Decimal("-1"))

    def test_both_sides_none_is_not_a_break(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, None, None, as_of=T0)
        assert result.is_break is False
        assert result.internal_quantity is None
        assert result.street_quantity is None

    def test_missing_internal_side_with_real_street_position_is_a_break(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, None, _position("100"), as_of=T0)
        assert result.is_break is True
        assert result.internal_quantity is None
        assert result.difference == Decimal("100")

    def test_missing_street_side_with_real_internal_position_is_a_break(self) -> None:
        engine = ReconciliationEngine()
        result = engine.reconcile(AAPL, _position("100"), None, as_of=T0)
        assert result.is_break is True
        assert result.difference == Decimal("-100")

    def test_instrument_mismatch_on_internal_position_raises(self) -> None:
        engine = ReconciliationEngine()
        with pytest.raises(ValueError, match="does not match"):
            engine.reconcile(AAPL, _position("100", instrument=MSFT), _position("100"), as_of=T0)

    def test_instrument_mismatch_on_street_position_raises(self) -> None:
        engine = ReconciliationEngine()
        with pytest.raises(ValueError, match="does not match"):
            engine.reconcile(AAPL, _position("100"), _position("100", instrument=MSFT), as_of=T0)

    def test_naive_as_of_rejected(self) -> None:
        engine = ReconciliationEngine()
        with pytest.raises(ValueError, match="timezone-aware"):
            engine.reconcile(AAPL, _position("100"), _position("100"), as_of=datetime(2026, 8, 5))
