"""Compares an internal position against a street position and produces a ReconciliationResult.

Invocation-agnostic per Decision 5 (docs/architecture.md): this class
has no knowledge of Redis, schedulers, or the replay engine. It takes
two optional Positions and returns a result -- streaming, scheduled,
and replay-driven callers are all thin adapters over this same engine.
"""

from datetime import datetime
from decimal import Decimal

from concord_core.domain.position import Position
from concord_core.domain.reconciliation import ReconciliationResult
from concord_core.domain.temporal import require_utc
from concord_core.domain.value_objects import Instrument


class ReconciliationEngine:
    def __init__(self, tolerance: Decimal = Decimal("0")) -> None:
        if tolerance < 0:
            raise ValueError("tolerance must not be negative")
        self._tolerance = tolerance

    def reconcile(
        self,
        instrument: Instrument,
        internal_position: Position | None,
        street_position: Position | None,
        as_of: datetime,
    ) -> ReconciliationResult:
        require_utc(as_of)
        self._require_matching_instrument(instrument, internal_position)
        self._require_matching_instrument(instrument, street_position)

        internal_quantity = internal_position.quantity if internal_position is not None else None
        street_quantity = street_position.quantity if street_position is not None else None

        effective_internal = internal_quantity if internal_quantity is not None else Decimal("0")
        effective_street = street_quantity if street_quantity is not None else Decimal("0")
        difference = effective_street - effective_internal
        is_break = abs(difference) > self._tolerance

        return ReconciliationResult(
            instrument=instrument,
            internal_quantity=internal_quantity,
            street_quantity=street_quantity,
            difference=difference,
            is_break=is_break,
            as_of=as_of,
        )

    @staticmethod
    def _require_matching_instrument(instrument: Instrument, position: Position | None) -> None:
        if position is not None and position.instrument != instrument:
            raise ValueError(
                f"position instrument {position.instrument.symbol} does not match "
                f"expected instrument {instrument.symbol}"
            )
