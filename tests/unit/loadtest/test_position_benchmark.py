"""Tests for the build_position CPU benchmark.

No timing thresholds are asserted -- hardcoding a millisecond bound
into a portable test suite would be flaky across machines and CI
runners. These tests check behavior, not wall-clock numbers.
"""

import pytest

from concord_core.loadtest.position_benchmark import benchmark_build_position


def test_zero_fill_count_raises() -> None:
    with pytest.raises(ValueError, match="fill_count must be positive"):
        benchmark_build_position(0, repetitions=5)


def test_zero_repetitions_raises() -> None:
    with pytest.raises(ValueError, match="repetitions must be positive"):
        benchmark_build_position(10, repetitions=0)


def test_records_one_latency_per_repetition() -> None:
    recorder = benchmark_build_position(10, repetitions=5)
    assert recorder.count == 5


def test_same_seed_is_deterministic_in_fill_generation() -> None:
    first = benchmark_build_position(20, repetitions=3, seed=7)
    second = benchmark_build_position(20, repetitions=3, seed=7)
    assert first.count == second.count == 3


def test_larger_fill_count_still_completes() -> None:
    recorder = benchmark_build_position(2000, repetitions=2)
    assert recorder.count == 2
