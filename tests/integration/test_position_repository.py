"""Integration tests for PositionSnapshotRepository against a live TimescaleDB instance."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import Position
from concord_core.domain.value_objects import Instrument
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.position_repository import PositionSnapshotRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


@pytest.fixture
async def repository():
    settings = DatabaseSettings()
    pool = await create_pool(settings)
    await apply_migrations(pool, MIGRATIONS_DIR)
    yield PositionSnapshotRepository(pool)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE position_snapshots")
    await pool.close()


async def test_get_latest_returns_none_when_no_snapshot_exists(
    repository: PositionSnapshotRepository,
) -> None:
    assert await repository.get_latest(AAPL) is None


async def test_insert_then_get_latest_round_trips(
    repository: PositionSnapshotRepository,
) -> None:
    position = Position(instrument=AAPL, quantity=Decimal("100"), as_of=T0)
    await repository.insert_snapshot(position)
    assert await repository.get_latest(AAPL) == position


async def test_get_latest_returns_most_recent_snapshot(
    repository: PositionSnapshotRepository,
) -> None:
    earlier = Position(instrument=AAPL, quantity=Decimal("100"), as_of=T0)
    later = Position(instrument=AAPL, quantity=Decimal("150"), as_of=T0 + timedelta(hours=1))
    await repository.insert_snapshot(earlier)
    await repository.insert_snapshot(later)
    assert await repository.get_latest(AAPL) == later


async def test_insert_snapshot_is_idempotent(repository: PositionSnapshotRepository) -> None:
    position = Position(instrument=AAPL, quantity=Decimal("100"), as_of=T0)
    await repository.insert_snapshot(position)
    await repository.insert_snapshot(position)  # must not raise or duplicate
    assert await repository.get_latest(AAPL) == position
