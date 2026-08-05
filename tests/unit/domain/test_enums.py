"""Tests for core domain enumerations.

These enums are a wire-format contract, not just a vocabulary list.
Every test here exists to protect a specific promise made in
enums.py's docstring: that these values serialize cleanly to JSON and
onto Redis Streams, and that their exact string values are stable.
Changing an enum member's value here is a breaking change for every
downstream consumer -- these tests make that impossible to do by
accident.
"""

import json

from concord_core.domain.enums import InstrumentType, Side, TradeStatus


class TestSide:
    def test_members_have_expected_string_values(self) -> None:
        assert Side.BUY == "BUY"
        assert Side.SELL == "SELL"

    def test_is_instance_of_str(self) -> None:
        """StrEnum members must be real strings, not str-like wrappers.

        This is what makes them safe to drop directly into a Redis
        XADD call or a Pydantic model without a `.value` conversion
        step -- and it's the entire reason we chose StrEnum over a
        plain Enum in the first place.
        """
        assert isinstance(Side.BUY, str)

    def test_serializes_to_json_without_value_extraction(self) -> None:
        payload = {"side": Side.BUY}
        assert json.dumps(payload) == '{"side": "BUY"}'


class TestInstrumentType:
    def test_members_have_expected_string_values(self) -> None:
        assert InstrumentType.EQUITY == "EQUITY"
        assert InstrumentType.FUTURE == "FUTURE"
        assert InstrumentType.OPTION == "OPTION"
        assert InstrumentType.FX == "FX"

    def test_serializes_to_json_without_value_extraction(self) -> None:
        payload = {"instrument_type": InstrumentType.FUTURE}
        assert json.dumps(payload) == '{"instrument_type": "FUTURE"}'


class TestTradeStatus:
    def test_members_have_expected_string_values(self) -> None:
        assert TradeStatus.NEW == "NEW"
        assert TradeStatus.CANCELLED == "CANCELLED"
        assert TradeStatus.CORRECTED == "CORRECTED"

    def test_serializes_to_json_without_value_extraction(self) -> None:
        payload = {"status": TradeStatus.CORRECTED}
        assert json.dumps(payload) == '{"status": "CORRECTED"}'
