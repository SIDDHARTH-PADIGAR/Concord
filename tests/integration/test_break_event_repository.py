"""Integration tests for BreakEventRepository against a live TimescaleDB instance."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.storage.break_event_repository import BreakEventRepository
from concord_core.storage.database import apply_migrations, create_pool

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


@pytest.fixture
async def repository():
    settings = DatabaseSettings()
    pool = await create_pool(settings)
    await apply_migrations(pool, MIGRATIONS_DIR)
    yield BreakEventRepository(pool)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE break_events")
    await pool.close()


async def test_get_latest_returns_none_when_no_events_exist(
    repository: BreakEventRepository,
) -> None:
    assert await repository.get_latest_break_event(AAPL) is None


async def test_insert_then_get_latest_round_trips(repository: BreakEventRepository) -> None:
    event = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    await repository.insert_break_event(event)
    assert await repository.get_latest_break_event(AAPL) == event


async def test_get_latest_returns_most_recent_event(repository: BreakEventRepository) -> None:
    raised = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    resolved = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RESOLVED,
        difference=Decimal("0"),
        detected_at=T0 + timedelta(hours=1),
    )
    await repository.insert_break_event(raised)
    await repository.insert_break_event(resolved)
    assert await repository.get_latest_break_event(AAPL) == resolved


async def test_insert_break_event_is_idempotent(repository: BreakEventRepository) -> None:
    event = BreakEvent(
        break_id="BRK-1",
        instrument=AAPL,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )
    await repository.insert_break_event(event)
    await repository.insert_break_event(event)  # must not raise or duplicate
    assert await repository.get_latest_break_event(AAPL) == event
