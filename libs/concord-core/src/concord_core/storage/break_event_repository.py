"""TimescaleDB-backed repository for the BreakEvent history."""

import asyncpg

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.value_objects import Instrument

_INSERT_SQL = """
INSERT INTO break_events (break_id, symbol, instrument_type, status, difference, detected_at)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (break_id, status, detected_at) DO NOTHING
"""

_SELECT_LATEST_SQL = """
SELECT * FROM break_events
WHERE symbol = $1 AND instrument_type = $2
ORDER BY detected_at DESC
LIMIT 1
"""


def _row_to_break_event(row: asyncpg.Record) -> BreakEvent:
    return BreakEvent(
        break_id=row["break_id"],
        instrument=Instrument(symbol=row["symbol"], instrument_type=row["instrument_type"]),
        status=BreakStatus(row["status"]),
        difference=row["difference"],
        detected_at=row["detected_at"],
    )


class BreakEventRepository:
    """Append-only access to the BreakEvent history. Satisfies both
    BreakEventSource and BreakEventSink structurally (Protocol-based),
    same as FillRepository does for FillSource/FillSink.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert_break_event(self, event: BreakEvent) -> None:
        await self._pool.execute(
            _INSERT_SQL,
            event.break_id,
            event.instrument.symbol,
            event.instrument.instrument_type.value,
            event.status.value,
            event.difference,
            event.detected_at,
        )

    async def get_latest_break_event(self, instrument: Instrument) -> BreakEvent | None:
        row = await self._pool.fetchrow(
            _SELECT_LATEST_SQL, instrument.symbol, instrument.instrument_type.value
        )
        return _row_to_break_event(row) if row is not None else None
