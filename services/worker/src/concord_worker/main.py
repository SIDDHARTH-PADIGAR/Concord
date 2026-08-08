"""Entrypoint for the Concord fill-ingestion worker process."""

import asyncio
import logging
import os
import socket

from concord_worker.app import run_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _consumer_name() -> str:
    return os.environ.get("CONCORD_WORKER_CONSUMER_NAME", socket.gethostname())


if __name__ == "__main__":
    asyncio.run(run_worker(_consumer_name()))
