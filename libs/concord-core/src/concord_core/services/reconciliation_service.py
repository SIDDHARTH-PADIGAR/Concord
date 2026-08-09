"""Orchestrates internal position, street position, comparison, and break lifecycle
into one invocation-agnostic entrypoint (Decision 5, docs/architecture.md).

Streaming triggers, scheduled/EOD jobs, and the replay engine (later
tasks) are all thin adapters calling reconcile_instrument() the same
way -- none of them duplicate this comparison logic themselves.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from concord_core.domain.breaks import BreakEvent
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument
from concord_core.services.break_detector import BreakDetector
from concord_core.services.reconciliation_engine import ReconciliationEngine


class InternalPositionSource(Protocol):
    async def compute_position(self, instrument: Instrument) -> Position | None: ...


class StreetPositionSource(Protocol):
    """No concrete implementation exists yet -- see docs/architecture.md,
    Deferred Extension Points. We don't yet know whether street data
    will come from a simulated fill store, a FIX drop-copy, or a file
    feed, so the concrete adapter is deliberately not built until one
    of those becomes a real requirement.
    """

    async def get_position(self, instrument: Instrument) -> Position | None: ...


class ReconciliationService:
    def __init__(
        self,
        internal_source: InternalPositionSource,
        street_source: StreetPositionSource,
        engine: ReconciliationEngine,
        break_detector: BreakDetector,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._internal_source = internal_source
        self._street_source = street_source
        self._engine = engine
        self._break_detector = break_detector
        self._clock = clock

    async def reconcile_instrument(self, instrument: Instrument) -> BreakEvent | None:
        internal_position = await self._internal_source.compute_position(instrument)
        street_position = await self._street_source.get_position(instrument)
        as_of = self._clock()

        result = self._engine.reconcile(instrument, internal_position, street_position, as_of)
        return await self._break_detector.detect(instrument, result)
