"""Integration test for the deployable worker's wiring (build_worker).

Exercises the actual entrypoint construction path (env-var-driven
settings, migrations, real Redis + TimescaleDB) end-to-end -- distinct
from test_fill_ingestion_consumer.py, which covers FillIngestionConsumer's
internal logic directly. This test proves build_worker() wires those
pieces together correctly, the way the real Docker entrypoint does.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository
from concord_worker.app import GROUP, STREAM, build_worker

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)

pytestmark = pytest.mark.integration


def _fill(execution_id: str = "EX-1") -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=AAPL,
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150"),
        executed_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC),
        status=TradeStatus.NEW,
    )


@pytest.fixture
async def wiring():
    redis_client = create_redis_client(RedisSettings())
    publisher = RedisStreamClient(redis_client)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    verifier = FillRepository(db_pool)

    yield publisher, verifier

    await redis_client.delete(STREAM)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE fills")
    await db_pool.close()
    await redis_client.aclose()


async def test_build_worker_consumes_and_persists_a_real_published_fill(wiring) -> None:
    publisher, verifier = wiring
    fill = _fill()

    consumer = await build_worker(consumer_name="worker-test-1")
    await publisher.ensure_consumer_group(STREAM, GROUP)
    await publisher.publish(STREAM, fill)

    processed_count = await consumer.process_once(block_ms=1000)

    assert processed_count == 1
    persisted = await verifier.get_by_execution_id(fill.exchange_execution_id)
    assert persisted == fill
