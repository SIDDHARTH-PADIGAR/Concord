"""End-to-end integration test: real internal + street fills, through the
full ReconciliationService -> ReconciliationEngine -> BreakDetector
pipeline, persisted via real repositories.

This is the first test proving the whole Milestone 3 pipeline works
together against live infrastructure, not just each piece in isolation.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.domain.breaks import BreakStatus
from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.services.break_detector import BreakDetector
from concord_core.services.position_service import PositionService
from concord_core.services.reconciliation_engine import ReconciliationEngine
from concord_core.services.reconciliation_service import ReconciliationService
from concord_core.services.street_position_source import StreetPositionSourceAdapter
from concord_core.storage.break_event_repository import BreakEventRepository
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository
from concord_core.storage.position_repository import PositionSnapshotRepository
from concord_core.storage.street_fill_repository import StreetFillRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
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
async def pipeline():
    pool = await create_pool(DatabaseSettings())
    await apply_migrations(pool, MIGRATIONS_DIR)

    internal_repo = FillRepository(pool)
    street_repo = StreetFillRepository(pool)
    snapshot_repo = PositionSnapshotRepository(pool)
    break_repo = BreakEventRepository(pool)

    service = ReconciliationService(
        internal_source=PositionService(internal_repo, snapshot_repo),
        street_source=StreetPositionSourceAdapter(street_repo),
        engine=ReconciliationEngine(),
        break_detector=BreakDetector(break_repo, break_repo),
        clock=lambda: T0,
    )

    yield service, internal_repo, street_repo, break_repo

    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE fills, street_fills, break_events, position_snapshots")
    await pool.close()


async def test_matching_internal_and_street_fills_produce_no_break(pipeline) -> None:
    service, internal_repo, street_repo, _break_repo = pipeline
    await internal_repo.insert_fill(_fill("EX-1", "100"))
    await street_repo.insert_fill(_fill("EX-1", "100"))

    event = await service.reconcile_instrument(AAPL)

    assert event is None
    assert await _break_repo.get_latest_break_event(AAPL) is None


async def test_mismatched_quantities_raise_a_break(pipeline) -> None:
    service, internal_repo, street_repo, _break_repo = pipeline
    await internal_repo.insert_fill(_fill("EX-1", "100"))
    await street_repo.insert_fill(_fill("EX-1", "90"))

    event = await service.reconcile_instrument(AAPL)

    assert event is not None
    assert event.status == BreakStatus.RAISED
    persisted = await _break_repo.get_latest_break_event(AAPL)
    assert persisted == event


async def test_correcting_street_side_resolves_the_break(pipeline) -> None:
    service, internal_repo, street_repo, _break_repo = pipeline
    await internal_repo.insert_fill(_fill("EX-1", "100"))
    await street_repo.insert_fill(_fill("EX-1", "90"))
    raised = await service.reconcile_instrument(AAPL)
    assert raised is not None
    assert raised.status == BreakStatus.RAISED

    await street_repo.insert_fill(
        Fill(
            exchange_execution_id="EX-2",
            trade_id="TR-1",
            instrument=AAPL,
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
            executed_at=T0,
            status=TradeStatus.CORRECTED,
            corrects_execution_id="EX-1",
        )
    )
    resolved = await service.reconcile_instrument(AAPL)

    assert resolved is not None
    assert resolved.status == BreakStatus.RESOLVED
    assert resolved.break_id == raised.break_id
