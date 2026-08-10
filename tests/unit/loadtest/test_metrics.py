"""Tests for LatencyRecorder."""

import time

import pytest

from concord_core.loadtest.metrics import LatencyRecorder


def test_elapsed_seconds_requires_start_and_stop() -> None:
    recorder = LatencyRecorder()
    with pytest.raises(ValueError, match=r"start\(\) and stop\(\)"):
        _ = recorder.elapsed_seconds


def test_elapsed_seconds_measures_start_to_stop() -> None:
    recorder = LatencyRecorder()
    recorder.start()
    time.sleep(0.01)
    recorder.stop()
    assert recorder.elapsed_seconds >= 0.01


def test_count_reflects_number_of_recorded_latencies() -> None:
    recorder = LatencyRecorder()
    recorder.record(0.001)
    recorder.record(0.002)
    assert recorder.count == 2


def test_throughput_per_second_computed_from_count_and_elapsed() -> None:
    recorder = LatencyRecorder()
    recorder.start()
    for _ in range(10):
        recorder.record(0.001)
    recorder.stop()
    assert recorder.throughput_per_second == pytest.approx(10 / recorder.elapsed_seconds)


def test_throughput_raises_when_elapsed_is_zero() -> None:
    """Elapsed-exactly-zero is essentially unreachable via real start()/stop()
    calls, so this reaches into private state deliberately to force the
    edge case rather than relying on a flaky tight timing loop.
    """
    recorder = LatencyRecorder()
    fixed_time = time.perf_counter()
    recorder._start_time = fixed_time
    recorder._end_time = fixed_time
    recorder.record(0.001)
    with pytest.raises(ValueError, match="positive"):
        _ = recorder.throughput_per_second


def test_percentile_raises_with_no_data() -> None:
    recorder = LatencyRecorder()
    with pytest.raises(ValueError, match="no latencies recorded"):
        recorder.percentile(50)


def test_percentile_out_of_range_raises() -> None:
    recorder = LatencyRecorder()
    recorder.record(0.001)
    with pytest.raises(ValueError, match="between 0 and 100"):
        recorder.percentile(101)


def test_percentile_min_and_max() -> None:
    recorder = LatencyRecorder()
    for value in [0.005, 0.001, 0.003, 0.002, 0.004]:
        recorder.record(value)
    assert recorder.percentile(0) == pytest.approx(0.001)
    assert recorder.percentile(100) == pytest.approx(0.005)


def test_summary_contains_expected_keys() -> None:
    recorder = LatencyRecorder()
    recorder.start()
    for value in [0.001, 0.002, 0.003]:
        recorder.record(value)
    recorder.stop()
    summary = recorder.summary()
    assert set(summary.keys()) == {
        "count",
        "elapsed_seconds",
        "throughput_per_second",
        "min_ms",
        "max_ms",
        "mean_ms",
        "p50_ms",
        "p95_ms",
        "p99_ms",
    }
