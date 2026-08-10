"""Benchmarks the real fill-ingestion pipeline: Redis publish throughput and
FillIngestionConsumer's consume+persist throughput.

Unlike position_benchmark.py (pure in-memory CPU cost), this measures
the actual I/O-bound path -- the concrete "Load Harness" component
named in the architecture diagram, and the evidence the Backpressure
and Batching Deferred Extension Points (docs/architecture.md) are
waiting on.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.loadtest.metrics import LatencyRecorder
from concord_core.simulation.market_data_simulator import generate_base_fill_history

_BENCHMARK_INSTRUMENT = Instrument(symbol="BENCH", instrument_type=InstrumentType.EQUITY)
_BENCHMARK_START_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class FillPublisher(Protocol):
    async def publish(self, stream: str, fill: Fill) -> str: ...


class BatchProcessor(Protocol):
    async def process_once(self, block_ms: int = 5000) -> int: ...


@dataclass(frozen=True)
class IngestionBenchmarkResult:
    """batch_latencies times each process_once() call (a batch of up to
    10 fills, per FillIngestionConsumer's fixed read count) -- NOT one
    latency per fill. fills_per_second is computed separately from the
    actual fill count, not from batch_latencies.throughput_per_second,
    which would report batches/sec instead.
    """

    batch_latencies: LatencyRecorder
    fills_processed: int
    elapsed_seconds: float

    @property
    def fills_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            raise ValueError("elapsed_seconds must be positive to compute throughput")
        return self.fills_processed / self.elapsed_seconds


async def benchmark_publish_throughput(
    publisher: FillPublisher, stream: str, fill_count: int, *, seed: int = 1
) -> LatencyRecorder:
    """Times fill_count individual publish() calls. Fill generation
    happens once, outside the timed region.
    """
    if fill_count <= 0:
        raise ValueError("fill_count must be positive")

    fills = generate_base_fill_history(
        _BENCHMARK_INSTRUMENT, "BENCH-TR", fill_count, seed=seed, start_time=_BENCHMARK_START_TIME
    )

    recorder = LatencyRecorder()
    recorder.start()
    for fill in fills:
        iteration_start = time.perf_counter()
        await publisher.publish(stream, fill)
        recorder.record(time.perf_counter() - iteration_start)
    recorder.stop()
    return recorder


async def benchmark_ingestion_throughput(
    processor: BatchProcessor, expected_count: int, *, block_ms: int = 1000
) -> IngestionBenchmarkResult:
    """Drains up to expected_count fills via repeated process_once()
    calls. Stops early if a batch returns 0 (stream exhausted) rather
    than waiting out block_ms with nothing left to read.

    Caller is responsible for ensuring the consumer group exists first
    -- process_once() itself doesn't do this, matching Task 7's
    existing FillIngestionConsumer contract.
    """
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    batch_latencies = LatencyRecorder()
    batch_latencies.start()
    processed = 0
    while processed < expected_count:
        batch_start = time.perf_counter()
        batch_size = await processor.process_once(block_ms=block_ms)
        batch_latencies.record(time.perf_counter() - batch_start)
        if batch_size == 0:
            break
        processed += batch_size
    batch_latencies.stop()

    return IngestionBenchmarkResult(
        batch_latencies=batch_latencies,
        fills_processed=processed,
        elapsed_seconds=batch_latencies.elapsed_seconds,
    )
