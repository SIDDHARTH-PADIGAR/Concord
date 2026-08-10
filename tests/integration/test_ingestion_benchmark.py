"""Integration test: the ingestion benchmark functions against real Redis + TimescaleDB.

Checks functional correctness (right counts consumed/persisted) --
not timing thresholds, consistent with every other benchmark test.
"""

from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.loadtest.ingestion_benchmark import (
    benchmark_ingestion_throughput,
    benchmark_publish_throughput,
)
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.services.fill_ingestion_consumer import FillIngestionConsumer
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"
STREAM = "fills-ingestion-benchmark-test"
GROUP = "fill-workers-ingestion-benchmark-test"
BENCH_INSTRUMENT = Instrument(symbol="BENCH", instrument_type=InstrumentType.EQUITY)

pytestmark = pytest.mark.integration


@pytest.fixture
async def wiring():
    redis_client = create_redis_client(RedisSettings())
    stream_client = RedisStreamClient(redis_client)
    await stream_client.ensure_consumer_group(STREAM, GROUP)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    fill_repository = FillRepository(db_pool)

    yield stream_client, fill_repository

    await redis_client.delete(STREAM)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE fills")
    await db_pool.close()
    await redis_client.aclose()


async def test_publish_then_ingest_processes_every_fill(wiring) -> None:
    stream_client, fill_repository = wiring
    fill_count = 25

    publish_recorder = await benchmark_publish_throughput(stream_client, STREAM, fill_count)
    assert publish_recorder.count == fill_count

    consumer = FillIngestionConsumer(
        stream_client, fill_repository, STREAM, GROUP, "benchmark-test-consumer"
    )
    result = await benchmark_ingestion_throughput(consumer, expected_count=fill_count)

    assert result.fills_processed == fill_count
    persisted = await fill_repository.get_by_instrument(BENCH_INSTRUMENT)
    assert len(persisted) == fill_count
