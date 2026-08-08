"""Tests for market data simulation: generation determinism and divergence semantics."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import build_position
from concord_core.domain.value_objects import Instrument
from concord_core.simulation.market_data_simulator import (
    DivergenceType,
    apply_divergence,
    generate_base_fill_history,
    generate_randomized_fill_history,
)

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
MSFT = Instrument(symbol="MSFT", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


class TestGenerateBaseFillHistory:
    def test_same_seed_produces_identical_output(self) -> None:
        first = generate_base_fill_history(AAPL, "TR-1", 20, seed=42, start_time=T0)
        second = generate_base_fill_history(AAPL, "TR-1", 20, seed=42, start_time=T0)
        assert first == second

    def test_different_seed_produces_different_output(self) -> None:
        first = generate_base_fill_history(AAPL, "TR-1", 20, seed=1, start_time=T0)
        second = generate_base_fill_history(AAPL, "TR-1", 20, seed=2, start_time=T0)
        assert first != second

    def test_zero_fill_count_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            generate_base_fill_history(AAPL, "TR-1", 0, seed=1, start_time=T0)

    def test_produces_requested_count(self) -> None:
        fills = generate_base_fill_history(AAPL, "TR-1", 15, seed=1, start_time=T0)
        assert len(fills) == 15


class TestApplyDivergence:
    def test_empty_base_fills_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            apply_divergence([], {})

    def test_mixed_instruments_raises(self) -> None:
        aapl_fill = generate_base_fill_history(AAPL, "TR-1", 1, seed=1, start_time=T0)[0]
        msft_fill = generate_base_fill_history(MSFT, "TR-1", 1, seed=2, start_time=T0)[0]
        with pytest.raises(ValueError, match="same instrument"):
            apply_divergence([aapl_fill, msft_fill], {})

    def test_no_divergence_produces_identical_histories_and_positions(self) -> None:
        base = generate_base_fill_history(AAPL, "TR-1", 10, seed=1, start_time=T0)
        history = apply_divergence(base, {})
        assert history.internal_fills == history.street_fills == base
        assert build_position(history.internal_fills) == build_position(history.street_fills)

    def test_missing_on_street_removes_fill_from_street_only(self) -> None:
        base = generate_base_fill_history(AAPL, "TR-1", 3, seed=1, start_time=T0)
        history = apply_divergence(base, {1: DivergenceType.MISSING_ON_STREET})

        assert len(history.internal_fills) == 3
        assert len(history.street_fills) == 2
        assert base[1] in history.internal_fills
        assert base[1] not in history.street_fills

    def test_missing_on_internal_removes_fill_from_internal_only(self) -> None:
        base = generate_base_fill_history(AAPL, "TR-1", 3, seed=1, start_time=T0)
        history = apply_divergence(base, {1: DivergenceType.MISSING_ON_INTERNAL})

        assert len(history.internal_fills) == 2
        assert len(history.street_fills) == 3
        assert base[1] not in history.internal_fills
        assert base[1] in history.street_fills

    def test_quantity_mismatch_offsets_street_quantity_only(self) -> None:
        base = generate_base_fill_history(AAPL, "TR-1", 1, seed=1, start_time=T0)
        history = apply_divergence(
            base, {0: DivergenceType.QUANTITY_MISMATCH}, quantity_mismatch_delta=Decimal("7")
        )

        internal_fill = history.internal_fills[0]
        street_fill = history.street_fills[0]
        assert internal_fill.exchange_execution_id == street_fill.exchange_execution_id
        assert street_fill.quantity == internal_fill.quantity + Decimal("7")

    def test_quantity_mismatch_produces_differing_positions(self) -> None:
        base = generate_base_fill_history(AAPL, "TR-1", 1, seed=1, start_time=T0)
        history = apply_divergence(
            base, {0: DivergenceType.QUANTITY_MISMATCH}, quantity_mismatch_delta=Decimal("10")
        )

        internal_position = build_position(history.internal_fills)
        street_position = build_position(history.street_fills)
        assert street_position.quantity - internal_position.quantity in (
            Decimal("10"),
            Decimal("-10"),
        )


class TestGenerateRandomizedFillHistory:
    def test_same_seed_produces_identical_output(self) -> None:
        kwargs = {
            "instrument": AAPL,
            "trade_id": "TR-1",
            "fill_count": 50,
            "seed": 7,
            "start_time": T0,
            "missing_on_street_probability": 0.1,
            "missing_on_internal_probability": 0.1,
            "quantity_mismatch_probability": 0.1,
        }
        first = generate_randomized_fill_history(**kwargs)
        second = generate_randomized_fill_history(**kwargs)
        assert first == second

    def test_zero_probabilities_produce_identical_histories(self) -> None:
        history = generate_randomized_fill_history(AAPL, "TR-1", 20, seed=1, start_time=T0)
        assert history.internal_fills == history.street_fills

    def test_probabilities_summing_above_one_raise(self) -> None:
        with pytest.raises(ValueError, match="between 0 and 1"):
            generate_randomized_fill_history(
                AAPL,
                "TR-1",
                10,
                seed=1,
                start_time=T0,
                missing_on_street_probability=0.6,
                quantity_mismatch_probability=0.6,
            )

    def test_nonzero_probability_produces_some_divergence(self) -> None:
        history = generate_randomized_fill_history(
            AAPL,
            "TR-1",
            100,
            seed=1,
            start_time=T0,
            quantity_mismatch_probability=1.0,
        )
        assert history.internal_fills != history.street_fills
