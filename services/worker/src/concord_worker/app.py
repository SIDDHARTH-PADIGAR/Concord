"""Wiring and lifecycle for the Concord fill-ingestion worker process."""

import asyncio
import logging
import signal
from pathlib import Path

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.services.fill_ingestion_consumer import FillIngestionConsumer
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository

logger = logging.getLogger(__name__)

STREAM = "fills"
GROUP = "fill-workers"
MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "sql"


async def build_worker(consumer_name: str) -> FillIngestionConsumer:
    """Wires a fully configured FillIngestionConsumer from environment settings.

    Kept separate from run_worker() so it's testable against real (or
    fake) infrastructure without needing signal handlers or an
    unbounded run loop.
    """
    redis_client = create_redis_client(RedisSettings())
    stream_client = RedisStreamClient(redis_client)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    fill_repository = FillRepository(db_pool)

    return FillIngestionConsumer(stream_client, fill_repository, STREAM, GROUP, consumer_name)


async def run_worker(consumer_name: str) -> None:
    """Runs the worker until SIGINT/SIGTERM.

    Thin by design: all business logic lives in FillIngestionConsumer
    (unit-tested in libs/concord-core) and build_worker() (integration-
    tested). This function only adds signal-driven shutdown -- stdlib
    plumbing, not domain logic worth a dedicated test.
    """
    consumer = await build_worker(consumer_name)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler isn't supported on Windows' ProactorEventLoop.
            # signal.signal() is less precise (fires outside the event loop)
            # but is sufficient for local dev; Docker/Linux uses the branch above.
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop_event.set))

    logger.info("worker %s starting, consuming stream=%s group=%s", consumer_name, STREAM, GROUP)
    await consumer.run_forever(stop_event)
    logger.info("worker %s shut down cleanly", consumer_name)
