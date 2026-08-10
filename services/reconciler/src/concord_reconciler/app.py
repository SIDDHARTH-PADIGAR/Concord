"""Wiring and lifecycle for the Concord scheduled reconciliation worker process."""

import asyncio
import logging
import signal
from pathlib import Path

from concord_core.config.settings import DatabaseSettings
from concord_core.services.break_detector import BreakDetector
from concord_core.services.position_service import PositionService
from concord_core.services.reconciliation_engine import ReconciliationEngine
from concord_core.services.reconciliation_scheduler import ReconciliationScheduler
from concord_core.services.reconciliation_service import ReconciliationService
from concord_core.services.street_position_source import StreetPositionSourceAdapter
from concord_core.storage.break_event_repository import BreakEventRepository
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository
from concord_core.storage.position_repository import PositionSnapshotRepository
from concord_core.storage.street_fill_repository import StreetFillRepository

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "sql"


async def build_reconciler() -> ReconciliationScheduler:
    """Wires a fully configured ReconciliationScheduler from environment
    settings. Kept separate from run_reconciler() so it's testable
    against real infrastructure without needing signal handlers or an
    unbounded run loop -- same split as concord_worker.app.build_worker.
    """
    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)

    fill_repository = FillRepository(db_pool)
    street_fill_repository = StreetFillRepository(db_pool)
    snapshot_repository = PositionSnapshotRepository(db_pool)
    break_repository = BreakEventRepository(db_pool)

    reconciliation_service = ReconciliationService(
        internal_source=PositionService(fill_repository, snapshot_repository),
        street_source=StreetPositionSourceAdapter(street_fill_repository),
        engine=ReconciliationEngine(),
        break_detector=BreakDetector(break_repository, break_repository),
    )

    return ReconciliationScheduler(
        reconciliation_service, [fill_repository, street_fill_repository]
    )


async def run_reconciler(interval_seconds: float) -> None:
    """Runs the reconciler until SIGINT/SIGTERM. Thin by design -- all
    business logic lives in ReconciliationScheduler (unit-tested in
    libs/concord-core) and build_reconciler() (integration-tested).
    """
    scheduler = await build_reconciler()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler isn't supported on Windows' ProactorEventLoop;
            # signal.signal() is sufficient for local dev (see concord_worker.app).
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop_event.set))

    logger.info("reconciler starting, interval=%ss", interval_seconds)
    await scheduler.run_forever(stop_event, interval_seconds)
    logger.info("reconciler shut down cleanly")
