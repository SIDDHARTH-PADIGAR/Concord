# Ingestion Pipeline Throughput Benchmark

Fill count: 1000

## Publish (Redis XADD, per-fill latency)

- Throughput: 606.45 fills/sec
- Mean: 1.647ms, p50: 1.519ms, p95: 2.129ms, p99: 4.125ms

## Ingestion (consume + persist, per-batch latency)

- Fills processed: 1000
- Throughput: 174.03 fills/sec
- Batch mean: 57.459ms, p50: 55.813ms, p95: 64.736ms, p99: 72.297ms
