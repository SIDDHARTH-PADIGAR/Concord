"""Consumes Fill events from a Redis Stream and persists them via a FillSink."""

import asyncio
import logging
from typing import Protocol

from concord_core.domain.entities import Fill

logger = logging.getLogger(__name__)


class StreamReader(Protocol):
    async def ensure_consumer_group(self, stream: str, group: str) -> None: ...

    async def read(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, Fill]]: ...

    async def ack(self, stream: str, group: str, message_id: str) -> None: ...


class FillSink(Protocol):
    async def insert_fill(self, fill: Fill) -> bool: ...


class FillIngestionConsumer:
    """Reads Fill events off a Redis Stream consumer group and persists them.

    A message is acked only after a successful insert. If the insert
    raises, the message is left unacked and stays pending for
    redelivery -- safe because FillSink.insert_fill is idempotent.
    """

    def __init__(
        self,
        stream_reader: StreamReader,
        fill_sink: FillSink,
        stream: str,
        group: str,
        consumer_name: str,
    ) -> None:
        self._stream_reader = stream_reader
        self._fill_sink = fill_sink
        self._stream = stream
        self._group = group
        self._consumer_name = consumer_name

    async def process_once(self, block_ms: int = 5000) -> int:
        """Reads and processes a single batch. Returns the number of
        messages read (including any that failed and were left unacked).

        This is the primitive run_forever loops on -- exposed publicly
        so tests and scripts can drive one deterministic cycle without
        needing a bounded background loop.
        """
        messages = await self._stream_reader.read(
            self._stream, self._group, self._consumer_name, block_ms=block_ms
        )
        for message_id, fill in messages:
            try:
                await self._process_one(message_id, fill)
            except Exception:
                logger.exception(
                    "failed to process message %s; leaving unacked for redelivery", message_id
                )
        return len(messages)

    async def run_forever(self, stop_event: asyncio.Event, block_ms: int = 5000) -> None:
        await self._stream_reader.ensure_consumer_group(self._stream, self._group)
        while not stop_event.is_set():
            await self.process_once(block_ms=block_ms)

    async def _process_one(self, message_id: str, fill: Fill) -> None:
        was_new = await self._fill_sink.insert_fill(fill)
        await self._stream_reader.ack(self._stream, self._group, message_id)
        if was_new:
            logger.info("ingested fill %s", fill.exchange_execution_id)
        else:
            logger.info("redelivered fill %s (already persisted)", fill.exchange_execution_id)
