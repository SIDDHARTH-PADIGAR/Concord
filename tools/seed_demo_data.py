"""CLI for seeding a paired internal/street fill history into a running Concord stack.

Usage:
    python tools/seed_demo_data.py --symbol AAPL --fill-count 50 --seed 1 \
        --quantity-mismatch-probability 0.1

Requires infra/docker-compose.yml's redis and timescaledb services
running. Publishes internal fills onto the real Redis fills stream --
a running `docker compose up worker` consumes them exactly as it
would in production; run `docker compose up reconciler` (or wait for
its next interval pass) to see resulting breaks in break_events.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.simulation.demo_seeder import seed_demo_data
from concord_core.simulation.market_data_simulator import generate_randomized_fill_history
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.street_fill_repository import StreetFillRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STREAM = "fills"
GROUP = "fill-workers"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "infra" / "sql"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--instrument-type",
        default=InstrumentType.EQUITY.value,
        choices=[t.value for t in InstrumentType],
    )
    parser.add_argument("--trade-id", default=None, help="Defaults to SYMBOL-DEMO-<seed>")
    parser.add_argument("--fill-count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--start-time",
        default=None,
        help="ISO 8601, must include a UTC offset (e.g. 2026-08-10T12:00:00+00:00). "
        "Defaults to now.",
    )
    parser.add_argument("--missing-on-street-probability", type=float, default=0.0)
    parser.add_argument("--missing-on-internal-probability", type=float, default=0.0)
    parser.add_argument("--quantity-mismatch-probability", type=float, default=0.0)
    return parser.parse_args()


async def _async_main(args: argparse.Namespace) -> None:
    instrument = Instrument(
        symbol=args.symbol, instrument_type=InstrumentType(args.instrument_type)
    )
    trade_id = args.trade_id or f"{args.symbol}-DEMO-{args.seed}"
    start_time = datetime.fromisoformat(args.start_time) if args.start_time else datetime.now(UTC)

    history = generate_randomized_fill_history(
        instrument,
        trade_id,
        args.fill_count,
        seed=args.seed,
        start_time=start_time,
        missing_on_street_probability=args.missing_on_street_probability,
        missing_on_internal_probability=args.missing_on_internal_probability,
        quantity_mismatch_probability=args.quantity_mismatch_probability,
    )

    redis_client = create_redis_client(RedisSettings())
    stream_client = RedisStreamClient(redis_client)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    street_repository = StreetFillRepository(db_pool)

    await seed_demo_data(history, stream_client, street_repository, STREAM, GROUP)

    logger.info(
        "seeded %s: %d internal fill(s) published to stream=%s, %d street fill(s) inserted",
        instrument.symbol,
        len(history.internal_fills),
        STREAM,
        len(history.street_fills),
    )

    await db_pool.close()
    await redis_client.aclose()


def main() -> None:
    asyncio.run(_async_main(_parse_args()))


if __name__ == "__main__":
    main()
