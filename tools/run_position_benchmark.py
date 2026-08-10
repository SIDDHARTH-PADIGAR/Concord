"""CLI: benchmarks build_position's cost across a range of fill-history sizes.

Usage:
    python tools/run_position_benchmark.py --fill-counts 10 100 1000 10000 --repetitions 50

Writes a markdown report to benchmarks/position_benchmark_<timestamp>.md
and prints a summary table to stdout.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from concord_core.loadtest.position_benchmark import benchmark_build_position

BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fill-counts", type=int, nargs="+", default=[10, 100, 1000, 10000])
    parser.add_argument("--repetitions", type=int, default=50)
    return parser.parse_args()


def _write_report(path: Path, repetitions: int, rows: list[tuple[int, dict[str, float]]]) -> None:
    lines = [
        "# build_position Benchmark",
        "",
        f"Repetitions per fill count: {repetitions}",
        "",
        "| Fill Count | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for fill_count, summary in rows:
        lines.append(
            f"| {fill_count} | {summary['mean_ms']} | {summary['p50_ms']} | "
            f"{summary['p95_ms']} | {summary['p99_ms']} | {summary['max_ms']} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = _parse_args()
    rows: list[tuple[int, dict[str, float]]] = []
    for fill_count in args.fill_counts:
        recorder = benchmark_build_position(fill_count, repetitions=args.repetitions)
        summary = recorder.summary()
        rows.append((fill_count, summary))
        print(
            f"fill_count={fill_count:>7} "
            f"mean={summary['mean_ms']:>9.3f}ms "
            f"p95={summary['p95_ms']:>9.3f}ms "
            f"p99={summary['p99_ms']:>9.3f}ms "
            f"max={summary['max_ms']:>9.3f}ms"
        )

    BENCHMARKS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = BENCHMARKS_DIR / f"position_benchmark_{timestamp}.md"
    _write_report(report_path, args.repetitions, rows)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
