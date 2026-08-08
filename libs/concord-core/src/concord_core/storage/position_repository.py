"""TimescaleDB-backed repository for Position snapshots."""

import asyncpg

from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument

_INSERT_SQL = """
INSERT INTO position_snapshots (symbol, instrument_type, quantity, as_of)
VALUES ($1, $2, $3, $4)
ON CONFLICT (symbol, instrument_type, as_of) DO NOTHING
"""

_SELECT_LATEST_SQL = """
SELECT * FROM position_snapshots
WHERE symbol = $1 AND instrument_type = $2
ORDER BY as_of DESC
LIMIT 1
"""


def _row_to_position(row: asyncpg.Record) -> Position:
    return Position(
        instrument=Instrument(
            symbol=row["symbol"],
            instrument_type=InstrumentType(row["instrument_type"]),
        ),
        quantity=row["quantity"],
        as_of=row["as_of"],
    )


class PositionSnapshotRepository:
    """Append-only access to computed Position snapshots.

    A snapshot is never updated in place -- inserting a Position with
    a newer as_of is how the "current" position changes. This mirrors
    the same event-sourced discipline already applied to Fills.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert_snapshot(self, position: Position) -> None:
        await self._pool.execute(
            _INSERT_SQL,
            position.instrument.symbol,
            position.instrument.instrument_type.value,
            position.quantity,
            position.as_of,
        )

    async def get_latest(self, instrument: Instrument) -> Position | None:
        row = await self._pool.fetchrow(
            _SELECT_LATEST_SQL, instrument.symbol, instrument.instrument_type.value
        )
        return _row_to_position(row) if row is not None else None
