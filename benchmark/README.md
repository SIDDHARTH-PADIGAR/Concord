# Benchmarks

Generated reports from `tools/run_*_benchmark.py` scripts land here,
one timestamped file per run. Committed to track how performance
characteristics evolve as the codebase changes -- these are historical
records, not something to hand-edit.

See `docs/architecture.md`, Decision 4, for the question these
benchmarks exist to answer: whether `build_position`'s CPU cost
justifies moving reconciliation work to a process pool.