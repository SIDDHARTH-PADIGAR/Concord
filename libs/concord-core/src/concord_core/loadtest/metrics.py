"""Latency and throughput measurement utilities for load testing.

Not thread-safe -- intended for single-asyncio-task or synchronous
single-threaded use, consistent with the rest of this codebase's
single-event-loop model.
"""

import statistics
import time


class LatencyRecorder:
    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._start_time: float | None = None
        self._end_time: float | None = None

    def start(self) -> None:
        self._start_time = time.perf_counter()

    def stop(self) -> None:
        self._end_time = time.perf_counter()

    def record(self, latency_seconds: float) -> None:
        self._latencies.append(latency_seconds)

    @property
    def count(self) -> int:
        return len(self._latencies)

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None or self._end_time is None:
            raise ValueError(
                "start() and stop() must both be called before reading elapsed_seconds"
            )
        return self._end_time - self._start_time

    @property
    def throughput_per_second(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed <= 0:
            raise ValueError("elapsed_seconds must be positive to compute throughput")
        return self.count / elapsed

    def percentile(self, p: float) -> float:
        if not self._latencies:
            raise ValueError("no latencies recorded")
        if not 0 <= p <= 100:
            raise ValueError("p must be between 0 and 100")
        sorted_latencies = sorted(self._latencies)
        index = min(round(p / 100 * (len(sorted_latencies) - 1)), len(sorted_latencies) - 1)
        return sorted_latencies[index]

    def summary(self) -> dict[str, float]:
        return {
            "count": float(self.count),
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "throughput_per_second": round(self.throughput_per_second, 2),
            "min_ms": round(min(self._latencies) * 1000, 3),
            "max_ms": round(max(self._latencies) * 1000, 3),
            "mean_ms": round(statistics.mean(self._latencies) * 1000, 3),
            "p50_ms": round(self.percentile(50) * 1000, 3),
            "p95_ms": round(self.percentile(95) * 1000, 3),
            "p99_ms": round(self.percentile(99) * 1000, 3),
        }
