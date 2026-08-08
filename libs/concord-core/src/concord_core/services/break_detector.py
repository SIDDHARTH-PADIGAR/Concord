"""Determines when a reconciliation result should raise or resolve a break.

Stateless per call -- all state lives in the BreakEvent history, read
via BreakEventSource. Mirrors Decision 5's invocation-agnostic
philosophy: this has no knowledge of who called it or how often.
"""

import uuid
from collections.abc import Callable
from typing import Protocol

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.reconciliation import ReconciliationResult
from concord_core.domain.value_objects import Instrument


class BreakEventSource(Protocol):
    async def get_latest_break_event(self, instrument: Instrument) -> BreakEvent | None: ...


class BreakEventSink(Protocol):
    async def insert_break_event(self, event: BreakEvent) -> None: ...


class BreakDetector:
    def __init__(
        self,
        source: BreakEventSource,
        sink: BreakEventSink,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._source = source
        self._sink = sink
        self._id_factory = id_factory

    async def detect(
        self, instrument: Instrument, result: ReconciliationResult
    ) -> BreakEvent | None:
        """Returns the BreakEvent emitted (RAISED or RESOLVED), or None
        if no state transition was needed -- e.g. already broken with
        an open break, or already fine with nothing open.
        """
        latest = await self._source.get_latest_break_event(instrument)
        currently_open = latest is not None and latest.status == BreakStatus.RAISED

        event: BreakEvent
        if result.is_break and not currently_open:
            event = BreakEvent(
                break_id=self._id_factory(),
                instrument=instrument,
                status=BreakStatus.RAISED,
                difference=result.difference,
                detected_at=result.as_of,
            )
        elif not result.is_break and currently_open:
            assert latest is not None
            event = BreakEvent(
                break_id=latest.break_id,
                instrument=instrument,
                status=BreakStatus.RESOLVED,
                difference=result.difference,
                detected_at=result.as_of,
            )
        else:
            return None

        await self._sink.insert_break_event(event)
        return event
