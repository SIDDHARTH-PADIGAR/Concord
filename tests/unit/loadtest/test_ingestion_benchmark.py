"""Unit tests for the ingestion benchmark using plain fakes -- no Redis, no database."""

import pytest

from concord_core.domain.entities import Fill
from concord_core.loadtest.ingestion_benchmark import (
    IngestionBenchmarkResult,
    benchmark_ingestion_throughput,
    benchmark_publish_throughput,
)

STREAM = "bench-stream"


class _FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, Fill]] = []

    async def publish(self, stream: str, fill: Fill) -> str:
        self.published.append((stream, fill))
        return f"msg-{len(self.published)}"


class _FakeBatchProcessor:
    def __init__(self, batch_sizes: list[int]) -> None:
        self._batch_sizes = list(batch_sizes)
        self.calls = 0

    async def process_once(self, block_ms: int = 5000) -> int:
        self.calls += 1
        if not self._batch_sizes:
            return 0
        return self._batch_sizes.pop(0)


class TestBenchmarkPublishThroughput:
    async def test_zero_fill_count_raises(self) -> None:
        with pytest.raises(ValueError, match="fill_count must be positive"):
            await benchmark_publish_throughput(_FakePublisher(), STREAM, 0)

    async def test_records_one_latency_per_fill(self) -> None:
        publisher = _FakePublisher()
        recorder = await benchmark_publish_throughput(publisher, STREAM, 5)
        assert recorder.count == 5
        assert len(publisher.published) == 5


class TestBenchmarkIngestionThroughput:
    async def test_zero_expected_count_raises(self) -> None:
        with pytest.raises(ValueError, match="expected_count must be positive"):
            await benchmark_ingestion_throughput(_FakeBatchProcessor([]), 0)

    async def test_stops_once_expected_count_reached(self) -> None:
        processor = _FakeBatchProcessor([10, 10, 5])  # sums to exactly 25
        result = await benchmark_ingestion_throughput(processor, expected_count=25)
        assert result.fills_processed == 25
        assert processor.calls == 3

    async def test_stops_early_when_a_batch_returns_zero(self) -> None:
        processor = _FakeBatchProcessor([10, 0])  # stream exhausted before reaching 100
        result = await benchmark_ingestion_throughput(processor, expected_count=100)
        assert result.fills_processed == 10
        assert processor.calls == 2

    async def test_batch_latencies_has_one_entry_per_process_once_call(self) -> None:
        processor = _FakeBatchProcessor([10, 10])
        result = await benchmark_ingestion_throughput(processor, expected_count=20)
        assert result.batch_latencies.count == 2


class TestIngestionBenchmarkResult:
    def test_fills_per_second_computed_from_fills_not_batches(self) -> None:
        from concord_core.loadtest.metrics import LatencyRecorder

        result = IngestionBenchmarkResult(
            batch_latencies=LatencyRecorder(), fills_processed=100, elapsed_seconds=2.0
        )
        assert result.fills_per_second == 50.0

    def test_raises_when_elapsed_seconds_is_zero(self) -> None:
        from concord_core.loadtest.metrics import LatencyRecorder

        result = IngestionBenchmarkResult(
            batch_latencies=LatencyRecorder(), fills_processed=10, elapsed_seconds=0.0
        )
        with pytest.raises(ValueError, match="positive"):
            _ = result.fills_per_second
