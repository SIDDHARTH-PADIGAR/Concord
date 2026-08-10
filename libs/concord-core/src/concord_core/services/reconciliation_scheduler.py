"""Runs ReconciliationService.reconcile_instrument across every known instrument
on a fixed interval -- the scheduled/EOD trigger from Decision 5 (docs/architecture.md).

One of three planned adapters over the same invocation-agnostic
ReconciliationService; streaming and replay-driven triggers are not
yet implemented (see Deferred Extension Points).
"""

import asyncio
import contextlib
import logging
from collections.abc import Sequence
from typing import Protocol

from concord_core.domain.breaks import BreakEvent
from concord_core.domain.value_objects import Instrument

logger = logging.getLogger(__name__)


class DistinctInstrumentSource(Protocol):
    async def get_distinct_instruments(self) -> list[Instrument]: ...


class ReconciliationInvoker(Protocol):
    async def reconcile_instrument(self, instrument: Instrument) -> BreakEvent | None: ...


class ReconciliationScheduler:
    """Depends on ReconciliationInvoker (satisfied structurally by
    ReconciliationService) and a set of DistinctInstrumentSources --
    same Protocol-based DI as every other orchestrator in this codebase.
    """

    def __init__(
        self,
        reconciler: ReconciliationInvoker,
        instrument_sources: Sequence[DistinctInstrumentSource],
    ) -> None:
        self._reconciler = reconciler
        self._instrument_sources = instrument_sources

    async def run_pass(self) -> list[BreakEvent]:
        """Reconciles every distinct instrument seen in any instrument
        source. Returns only the BreakEvents actually emitted (raised
        or resolved) -- most instruments, most passes, emit nothing.
        """
        instruments = await self._collect_distinct_instruments()
        events: list[BreakEvent] = []
        for instrument in instruments:
            event = await self._reconciler.reconcile_instrument(instrument)
            if event is not None:
                events.append(event)
                logger.info(
                    "break event: instrument=%s status=%s break_id=%s difference=%s",
                    instrument.symbol,
                    event.status,
                    event.break_id,
                    event.difference,
                )
        logger.info(
            "reconciliation pass complete: %d instrument(s) checked, %d break event(s) emitted",
            len(instruments),
            len(events),
        )
        return events

    async def run_forever(self, stop_event: asyncio.Event, interval_seconds: float) -> None:
        while not stop_event.is_set():
            await self.run_pass()
            with contextlib.suppress(TimeoutError):
                # interval elapsed without a stop request -- run another pass
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)

    async def _collect_distinct_instruments(self) -> list[Instrument]:
        seen: set[Instrument] = set()
        for source in self._instrument_sources:
            seen.update(await source.get_distinct_instruments())
        return sorted(seen, key=lambda instrument: instrument.symbol)
