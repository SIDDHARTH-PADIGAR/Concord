"""Integration test: seed_demo_data against real Redis + TimescaleDB."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.simulation.demo_seeder import seed_demo_data
from concord_core.simulation.market_data_simulator import generate_randomized_fill_history
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.street_fill_repository import StreetFillRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
STREAM = "fills-demo-seeder-test"
GROUP = "fill-workers-demo-seeder-test"
AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.integration


@pytest.fixture
async def wiring():
    redis_client = create_redis_client(RedisSettings())
    stream_client = RedisStreamClient(redis_client)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    street_repository = StreetFillRepository(db_pool)

    yield stream_client, street_repository

    await redis_client.delete(STREAM)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE street_fills")
    await db_pool.close()
    await redis_client.aclose()


async def test_seed_demo_data_publishes_and_persists_against_real_infra(wiring) -> None:
    stream_client, street_repository = wiring
    history = generate_randomized_fill_history(
        AAPL,
        "TR-DEMO",
        fill_count=10,
        seed=1,
        start_time=T0,
        quantity_mismatch_probability=0.3,
    )

    await seed_demo_data(history, stream_client, street_repository, STREAM, GROUP)

    consumed = await stream_client.read(STREAM, GROUP, "test-consumer", count=100, block_ms=100)
    assert len(consumed) == len(history.internal_fills)

    persisted_street_fills = await street_repository.get_by_trade_id("TR-DEMO")
    assert len(persisted_street_fills) == len(history.street_fills)
