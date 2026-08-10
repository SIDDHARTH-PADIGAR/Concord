"""Integration test for the deployable reconciler's wiring (build_reconciler)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.domain.breaks import BreakStatus
from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository
from concord_core.storage.street_fill_repository import StreetFillRepository
from concord_reconciler.app import MIGRATIONS_DIR, build_reconciler

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


def _fill(execution_id: str, quantity: str) -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=AAPL,
        side=Side.BUY,
        quantity=Decimal(quantity),
        price=Decimal("150"),
        executed_at=T0,
        status=TradeStatus.NEW,
    )


@pytest.fixture
async def wiring():
    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    internal_repo = FillRepository(db_pool)
    street_repo = StreetFillRepository(db_pool)

    yield internal_repo, street_repo

    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE fills, street_fills, break_events, position_snapshots")
    await db_pool.close()


async def test_build_reconciler_raises_a_break_for_a_real_mismatch(wiring) -> None:
    internal_repo, street_repo = wiring
    await internal_repo.insert_fill(_fill("EX-1", "100"))
    await street_repo.insert_fill(_fill("EX-1", "90"))

    scheduler = await build_reconciler()
    events = await scheduler.run_pass()

    assert len(events) == 1
    assert events[0].instrument == AAPL
    assert events[0].status == BreakStatus.RAISED
