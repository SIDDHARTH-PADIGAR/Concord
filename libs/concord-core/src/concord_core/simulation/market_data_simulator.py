"""Generates paired internal/street fill histories for testing reconciliation.

Both histories fold (via build_position) to the same net position under
normal conditions. Deliberately diverged fills are what give the
Reconciliation Engine and Break Detector real discrepancies to find.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from concord_core.domain.entities import Fill
from concord_core.domain.enums import Side, TradeStatus
from concord_core.domain.value_objects import Instrument


class DivergenceType(StrEnum):
    NONE = "NONE"
    MISSING_ON_STREET = "MISSING_ON_STREET"
    MISSING_ON_INTERNAL = "MISSING_ON_INTERNAL"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"


@dataclass(frozen=True)
class SimulatedFillHistory:
    """In-memory generation output -- not a wire-serialized entity, so a
    plain dataclass suffices here rather than a Pydantic model.
    """

    instrument: Instrument
    internal_fills: list[Fill]
    street_fills: list[Fill]


def generate_base_fill_history(
    instrument: Instrument,
    trade_id: str,
    fill_count: int,
    *,
    seed: int,
    start_time: datetime,
) -> list[Fill]:
    """Generates a single, internally-consistent sequence of fills.

    Pure and deterministic: the same seed always produces the same
    fills. This is the "ground truth" both internal and street
    histories are derived from before any divergence is applied.
    """
    if fill_count <= 0:
        raise ValueError("fill_count must be positive")

    rng = random.Random(seed)
    fills: list[Fill] = []
    current_time = start_time
    for i in range(fill_count):
        current_time += timedelta(seconds=rng.randint(1, 60))
        fills.append(
            Fill(
                exchange_execution_id=f"{trade_id}-EX-{i}",
                trade_id=trade_id,
                instrument=instrument,
                side=rng.choice([Side.BUY, Side.SELL]),
                quantity=Decimal(rng.randint(1, 100) * 10),
                price=Decimal(str(round(rng.uniform(50, 500), 2))),
                executed_at=current_time,
                status=TradeStatus.NEW,
            )
        )
    return fills


def apply_divergence(
    base_fills: Sequence[Fill],
    divergences: dict[int, DivergenceType],
    *,
    quantity_mismatch_delta: Decimal = Decimal("10"),
) -> SimulatedFillHistory:
    """Splits a base fill history into internal/street histories, applying
    an explicit divergence to specific fill indices. Deterministic --
    see generate_randomized_fill_history for the probabilistic wrapper.
    """
    if not base_fills:
        raise ValueError("base_fills must not be empty")
    instruments = {fill.instrument for fill in base_fills}
    if len(instruments) > 1:
        raise ValueError("all fills must reference the same instrument")

    internal_fills: list[Fill] = []
    street_fills: list[Fill] = []

    for index, fill in enumerate(base_fills):
        divergence = divergences.get(index, DivergenceType.NONE)

        if divergence == DivergenceType.MISSING_ON_STREET:
            internal_fills.append(fill)
        elif divergence == DivergenceType.MISSING_ON_INTERNAL:
            street_fills.append(fill)
        elif divergence == DivergenceType.QUANTITY_MISMATCH:
            internal_fills.append(fill)
            street_fills.append(
                fill.model_copy(update={"quantity": fill.quantity + quantity_mismatch_delta})
            )
        else:
            internal_fills.append(fill)
            street_fills.append(fill)

    return SimulatedFillHistory(
        instrument=next(iter(instruments)),
        internal_fills=internal_fills,
        street_fills=street_fills,
    )


def generate_randomized_fill_history(
    instrument: Instrument,
    trade_id: str,
    fill_count: int,
    *,
    seed: int,
    start_time: datetime,
    missing_on_street_probability: float = 0.0,
    missing_on_internal_probability: float = 0.0,
    quantity_mismatch_probability: float = 0.0,
) -> SimulatedFillHistory:
    """Convenience wrapper: generates a base history, then applies a
    randomized (but seed-reproducible) divergence per fill.
    """
    total_probability = (
        missing_on_street_probability
        + missing_on_internal_probability
        + quantity_mismatch_probability
    )
    if not 0.0 <= total_probability <= 1.0:
        raise ValueError(
            f"divergence probabilities must sum to between 0 and 1, got {total_probability}"
        )

    base_fills = generate_base_fill_history(
        instrument, trade_id, fill_count, seed=seed, start_time=start_time
    )
    rng = random.Random(seed + 1)  # distinct stream from generate_base_fill_history's own rng

    divergences: dict[int, DivergenceType] = {}
    for index in range(len(base_fills)):
        roll = rng.random()
        if roll < missing_on_street_probability:
            divergences[index] = DivergenceType.MISSING_ON_STREET
        elif roll < missing_on_street_probability + missing_on_internal_probability:
            divergences[index] = DivergenceType.MISSING_ON_INTERNAL
        elif roll < total_probability:
            divergences[index] = DivergenceType.QUANTITY_MISMATCH

    return apply_divergence(base_fills, divergences)
