"""Tests for domain value objects."""

import pytest
from pydantic import ValidationError

from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument


def test_valid_instrument_constructs() -> None:
    instrument = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
    assert instrument.symbol == "AAPL"


def test_empty_symbol_rejected() -> None:
    with pytest.raises(ValidationError):
        Instrument(symbol="", instrument_type=InstrumentType.EQUITY)


def test_instrument_is_frozen() -> None:
    instrument = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
    with pytest.raises(ValidationError):
        instrument.symbol = "MSFT"


def test_instrument_is_hashable() -> None:
    """Position aggregation will key dictionaries by Instrument -- it must be hashable."""
    a = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
    b = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
    assert hash(a) == hash(b)
    assert {a: "x"}[b] == "x"
