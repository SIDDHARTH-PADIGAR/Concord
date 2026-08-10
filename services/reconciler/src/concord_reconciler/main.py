"""Entrypoint for the Concord scheduled reconciliation worker process."""

import asyncio
import logging
import os

from concord_reconciler.app import run_reconciler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_DEFAULT_INTERVAL_SECONDS = 30.0


def _interval_seconds() -> float:
    return float(os.environ.get("CONCORD_RECONCILER_INTERVAL_SECONDS", _DEFAULT_INTERVAL_SECONDS))


if __name__ == "__main__":
    asyncio.run(run_reconciler(_interval_seconds()))
