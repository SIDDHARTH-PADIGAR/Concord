# Concord

A distributed post-trade reconciliation platform: independent services
ingest fills, build positions from an immutable event log, and
continuously reconcile internal-derived positions against a street
record — surfacing breaks when they disagree.

Architecture is documented in [`docs/architecture.md`](docs/architecture.md)
and is frozen as of Milestone 1. Changes to it require a documented
reason, not convenience.

## Status

Milestone 1, Task 1: repository scaffolding and tooling. No domain
code yet — this task exists to prove the format/lint/type/test
pipeline works before anything depends on it.

## Repository layout
concord/
├── libs/concord-core/ # shared domain models, config, cross-cutting concerns
├── services/ # independently deployable services (added from Milestone 2 on)
├── tests/ # unit and (later) integration tests
├── docs/ # architecture and design documentation
└── .github/workflows/ # CI

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\Activate.ps1 on Windows

pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e ./libs/concord-core

pre-commit install
```

## Running the quality gates

These four commands run in this exact order, locally and in CI. If any
of them fail, fix it before continuing — do not build on top of a
failing gate.

```bash
ruff format .
ruff check .
mypy libs/concord-core/src
pytest
```