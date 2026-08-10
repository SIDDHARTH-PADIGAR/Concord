"""TimescaleDB-backed repository for the street-side (exchange-reported) Fill event log.

Structurally near-identical to FillRepository -- see Deferred
Extension Points in docs/architecture.md for the tracked duplication.
"""

import asyncpg

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument

_INSERT_SQL = """
INSERT INTO street_fills (
    exchange_execution_id, trade_id, symbol, instrument_type, side,
    quantity, price, executed_at, status, corrects_execution_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (exchange_execution_id, executed_at) DO NOTHING
"""

_SELECT_BY_EXECUTION_ID_SQL = "SELECT * FROM street_fills WHERE exchange_execution_id = $1"
_SELECT_BY_TRADE_ID_SQL = "SELECT * FROM street_fills WHERE trade_id = $1 ORDER BY executed_at"
_SELECT_BY_INSTRUMENT_SQL = """
SELECT * FROM street_fills WHERE symbol = $1 AND instrument_type = $2 ORDER BY executed_at
"""
_SELECT_DISTINCT_INSTRUMENTS_SQL = "SELECT DISTINCT symbol, instrument_type FROM street_fills"


def _row_to_fill(row: asyncpg.Record) -> Fill:
    return Fill(
        exchange_execution_id=row["exchange_execution_id"],
        trade_id=row["trade_id"],
        instrument=Instrument(
            symbol=row["symbol"],
            instrument_type=InstrumentType(row["instrument_type"]),
        ),
        side=Side(row["side"]),
        quantity=row["quantity"],
        price=row["price"],
        executed_at=row["executed_at"],
        status=TradeStatus(row["status"]),
        corrects_execution_id=row["corrects_execution_id"],
    )


class StreetFillRepository:
    """Append-only access to the street-side Fill event log. Same
    idempotency reasoning as FillRepository: (exchange_execution_id,
    executed_at) as the conflict target.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert_fill(self, fill: Fill) -> bool:
        result: str = await self._pool.execute(
            _INSERT_SQL,
            fill.exchange_execution_id,
            fill.trade_id,
            fill.instrument.symbol,
            fill.instrument.instrument_type.value,
            fill.side.value,
            fill.quantity,
            fill.price,
            fill.executed_at,
            fill.status.value,
            fill.corrects_execution_id,
        )
        return result == "INSERT 0 1"

    async def get_by_execution_id(self, exchange_execution_id: str) -> Fill | None:
        row = await self._pool.fetchrow(_SELECT_BY_EXECUTION_ID_SQL, exchange_execution_id)
        return _row_to_fill(row) if row is not None else None

    async def get_by_trade_id(self, trade_id: str) -> list[Fill]:
        rows = await self._pool.fetch(_SELECT_BY_TRADE_ID_SQL, trade_id)
        return [_row_to_fill(row) for row in rows]

    async def get_by_instrument(self, instrument: Instrument) -> list[Fill]:
        rows = await self._pool.fetch(
            _SELECT_BY_INSTRUMENT_SQL, instrument.symbol, instrument.instrument_type.value
        )
        return [_row_to_fill(row) for row in rows]

    async def get_distinct_instruments(self) -> list[Instrument]:
        rows = await self._pool.fetch(_SELECT_DISTINCT_INSTRUMENTS_SQL)
        return [
            Instrument(symbol=row["symbol"], instrument_type=InstrumentType(row["instrument_type"]))
            for row in rows
        ]
