"""Integration test: real Redis Stream -> FillIngestionConsumer -> real TimescaleDB.

Uses process_once() rather than run_forever() so the test is bounded
and fast instead of riding out a full blocking read timeout.
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
from concord_core.services.fill_ingestion_consumer import FillIngestionConsumer
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
STREAM = "fills-test"
GROUP = "workers-test"
CONSUMER = "worker-test-1"
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
    stream_client = RedisStreamClient(redis_client)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    fill_repository = FillRepository(db_pool)

    yield stream_client, fill_repository

    await redis_client.delete(STREAM)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE fills")
    await db_pool.close()
    await redis_client.aclose()


async def test_published_fill_is_consumed_and_persisted(wiring) -> None:
    stream_client, fill_repository = wiring
    consumer = FillIngestionConsumer(stream_client, fill_repository, STREAM, GROUP, CONSUMER)
    fill = _fill()

    await stream_client.ensure_consumer_group(STREAM, GROUP)
    await stream_client.publish(STREAM, fill)

    processed_count = await consumer.process_once()

    assert processed_count == 1
    persisted = await fill_repository.get_by_execution_id(fill.exchange_execution_id)
    assert persisted == fill


async def test_process_once_with_no_pending_messages_returns_promptly(wiring) -> None:
    stream_client, fill_repository = wiring
    consumer = FillIngestionConsumer(stream_client, fill_repository, STREAM, GROUP, CONSUMER)

    await stream_client.ensure_consumer_group(STREAM, GROUP)

    processed_count = await consumer.process_once(block_ms=100)

    assert processed_count == 0
