"""Benchmarks build_position's raw computation cost as fill history size grows.

Directly measures the open question behind Decision 4 (docs/architecture.md):
build_position runs synchronously inside an async worker/reconciler
process -- every call blocks the event loop for its full duration.
This benchmark answers "how long, and does it scale badly enough to
justify multiprocessing" with actual numbers instead of assumption.
"""

import time
from datetime import UTC, datetime

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType
from concord_core.domain.position import build_position
from concord_core.domain.value_objects import Instrument
from concord_core.loadtest.metrics import LatencyRecorder
from concord_core.simulation.market_data_simulator import generate_base_fill_history

_BENCHMARK_INSTRUMENT = Instrument(symbol="BENCH", instrument_type=InstrumentType.EQUITY)
_BENCHMARK_START_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def benchmark_build_position(
    fill_count: int, *, repetitions: int, seed: int = 1
) -> LatencyRecorder:
    """Times `repetitions` calls to build_position against a fixed
    fill history of size fill_count. Fill generation happens once,
    outside the timed region -- only build_position's own cost is
    measured.
    """
    if fill_count <= 0:
        raise ValueError("fill_count must be positive")
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")

    fills: list[Fill] = generate_base_fill_history(
        _BENCHMARK_INSTRUMENT, "BENCH-TR", fill_count, seed=seed, start_time=_BENCHMARK_START_TIME
    )

    recorder = LatencyRecorder()
    recorder.start()
    for _ in range(repetitions):
        iteration_start = time.perf_counter()
        build_position(fills)
        recorder.record(time.perf_counter() - iteration_start)
    recorder.stop()
    return recorder
