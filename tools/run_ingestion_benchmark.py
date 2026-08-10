"""CLI: benchmarks real Redis publish throughput and FillIngestionConsumer's
consume+persist throughput against a running Concord stack.

Usage:
    python tools/run_ingestion_benchmark.py --fill-count 1000

Requires infra/docker-compose.yml's redis and timescaledb services
running, and no other consumer competing on the benchmark stream/group
(this script uses dedicated ones, so it's safe to run alongside a
running worker/reconciler).

Writes a markdown report to benchmarks/ingestion_benchmark_<timestamp>.md.
"""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from concord_core.config.settings import DatabaseSettings, RedisSettings
from concord_core.loadtest.ingestion_benchmark import (
    benchmark_ingestion_throughput,
    benchmark_publish_throughput,
)
from concord_core.messaging.redis_streams import RedisStreamClient, create_redis_client
from concord_core.services.fill_ingestion_consumer import FillIngestionConsumer
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository

BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "infra" / "sql"
STREAM = "fills-ingestion-benchmark"
GROUP = "fill-workers-ingestion-benchmark"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fill-count", type=int, default=1000)
    return parser.parse_args()


def _write_report(
    path: Path,
    fill_count: int,
    publish_summary: dict[str, float],
    fills_processed: int,
    fills_per_second: float,
    batch_summary: dict[str, float],
) -> None:
    lines = [
        "# Ingestion Pipeline Throughput Benchmark",
        "",
        f"Fill count: {fill_count}",
        "",
        "## Publish (Redis XADD, per-fill latency)",
        "",
        f"- Throughput: {publish_summary['throughput_per_second']} fills/sec",
        f"- Mean: {publish_summary['mean_ms']}ms, p50: {publish_summary['p50_ms']}ms, "
        f"p95: {publish_summary['p95_ms']}ms, p99: {publish_summary['p99_ms']}ms",
        "",
        "## Ingestion (consume + persist, per-batch latency)",
        "",
        f"- Fills processed: {fills_processed}",
        f"- Throughput: {round(fills_per_second, 2)} fills/sec",
        f"- Batch mean: {batch_summary['mean_ms']}ms, p50: {batch_summary['p50_ms']}ms, "
        f"p95: {batch_summary['p95_ms']}ms, p99: {batch_summary['p99_ms']}ms",
    ]
    path.write_text("\n".join(lines) + "\n")


async def _async_main(args: argparse.Namespace) -> None:
    redis_client = create_redis_client(RedisSettings())
    stream_client = RedisStreamClient(redis_client)
    await stream_client.ensure_consumer_group(STREAM, GROUP)

    db_pool = await create_pool(DatabaseSettings())
    await apply_migrations(db_pool, MIGRATIONS_DIR)
    fill_repository = FillRepository(db_pool)
    consumer = FillIngestionConsumer(
        stream_client, fill_repository, STREAM, GROUP, "benchmark-consumer"
    )

    print(f"Publishing {args.fill_count} fills...")
    publish_recorder = await benchmark_publish_throughput(stream_client, STREAM, args.fill_count)
    publish_summary = publish_recorder.summary()
    print(
        f"  throughput={publish_summary['throughput_per_second']:.1f}/s "
        f"p95={publish_summary['p95_ms']:.3f}ms"
    )

    print(f"Consuming and persisting {args.fill_count} fills...")
    result = await benchmark_ingestion_throughput(consumer, args.fill_count)
    batch_summary = result.batch_latencies.summary()
    print(
        f"  processed={result.fills_processed} "
        f"throughput={result.fills_per_second:.1f}/s "
        f"batch_p95={batch_summary['p95_ms']:.3f}ms"
    )

    BENCHMARKS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = BENCHMARKS_DIR / f"ingestion_benchmark_{timestamp}.md"
    _write_report(
        report_path,
        args.fill_count,
        publish_summary,
        result.fills_processed,
        result.fills_per_second,
        batch_summary,
    )
    print(f"\nReport written to {report_path}")

    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE fills")
    await redis_client.delete(STREAM)
    await db_pool.close()
    await redis_client.aclose()


def main() -> None:
    asyncio.run(_async_main(_parse_args()))


if __name__ == "__main__":
    main()
