"""Unit tests for FillIngestionConsumer using plain fakes -- no Redis, no database.

Covers the distributed-systems-relevant behavior directly: acking only
on success, leaving failed messages unacked, and idempotent-redelivery
handling.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.services.fill_ingestion_consumer import FillIngestionConsumer

STREAM = "fills"
GROUP = "workers"
CONSUMER = "worker-1"
AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)


def _fill(execution_id: str) -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=AAPL,
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150"),
        executed_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC),
        status=TradeStatus.NEW,
    )


class _FakeStreamReader:
    """Pops one batch per read() call; sets stop_event and returns [] once exhausted."""

    def __init__(self, batches: list[list[tuple[str, Fill]]], stop_event: asyncio.Event) -> None:
        self._batches = list(batches)
        self._stop_event = stop_event
        self.ensure_consumer_group_calls: list[tuple[str, str]] = []
        self.ack_calls: list[tuple[str, str, str]] = []

    async def ensure_consumer_group(self, stream: str, group: str) -> None:
        self.ensure_consumer_group_calls.append((stream, group))

    async def read(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, Fill]]:
        if not self._batches:
            self._stop_event.set()
            return []
        return self._batches.pop(0)

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        self.ack_calls.append((stream, group, message_id))


class _FakeFillSink:
    def __init__(self, raise_for: set[str] | None = None) -> None:
        self._raise_for = raise_for or set()
        self.inserted: list[Fill] = []

    async def insert_fill(self, fill: Fill) -> bool:
        if fill.exchange_execution_id in self._raise_for:
            raise RuntimeError("simulated transient DB failure")
        self.inserted.append(fill)
        return True


async def _run_bounded(reader: _FakeStreamReader, sink: _FakeFillSink) -> None:
    stop_event = asyncio.Event()
    reader._stop_event = stop_event
    consumer = FillIngestionConsumer(reader, sink, STREAM, GROUP, CONSUMER)
    await asyncio.wait_for(consumer.run_forever(stop_event), timeout=2.0)


async def test_processes_message_and_acks_it() -> None:
    stop_event = asyncio.Event()
    fill = _fill("EX-1")
    reader = _FakeStreamReader([[("msg-1", fill)]], stop_event)
    sink = _FakeFillSink()

    await _run_bounded(reader, sink)

    assert sink.inserted == [fill]
    assert reader.ack_calls == [(STREAM, GROUP, "msg-1")]


async def test_ensure_consumer_group_called_before_reading() -> None:
    stop_event = asyncio.Event()
    reader = _FakeStreamReader([], stop_event)
    sink = _FakeFillSink()

    await _run_bounded(reader, sink)

    assert reader.ensure_consumer_group_calls == [(STREAM, GROUP)]


async def test_redelivered_message_is_still_acked() -> None:
    """insert_fill returning False (duplicate) is a success path, not a failure."""
    stop_event = asyncio.Event()
    fill = _fill("EX-1")
    reader = _FakeStreamReader([[("msg-1", fill)]], stop_event)
    sink = _FakeFillSink()
    await sink.insert_fill(fill)  # pre-seed as already persisted

    await _run_bounded(reader, sink)

    assert reader.ack_calls == [(STREAM, GROUP, "msg-1")]


async def test_failed_insert_leaves_message_unacked() -> None:
    stop_event = asyncio.Event()
    fill = _fill("EX-1")
    reader = _FakeStreamReader([[("msg-1", fill)]], stop_event)
    sink = _FakeFillSink(raise_for={"EX-1"})

    await _run_bounded(reader, sink)

    assert reader.ack_calls == []


async def test_one_failed_message_does_not_block_the_rest_of_the_batch() -> None:
    stop_event = asyncio.Event()
    good_fill = _fill("EX-2")
    bad_fill = _fill("EX-1")
    reader = _FakeStreamReader([[("msg-1", bad_fill), ("msg-2", good_fill)]], stop_event)
    sink = _FakeFillSink(raise_for={"EX-1"})

    await _run_bounded(reader, sink)

    assert sink.inserted == [good_fill]
    assert reader.ack_calls == [(STREAM, GROUP, "msg-2")]


async def test_process_once_returns_message_count() -> None:
    stop_event = asyncio.Event()
    reader = _FakeStreamReader([[("msg-1", _fill("EX-1")), ("msg-2", _fill("EX-2"))]], stop_event)
    sink = _FakeFillSink()
    consumer = FillIngestionConsumer(reader, sink, STREAM, GROUP, CONSUMER)

    count = await consumer.process_once()

    assert count == 2


@pytest.mark.parametrize("empty_batches", [[]])
async def test_process_once_with_no_messages_returns_zero(
    empty_batches: list[list[tuple[str, Fill]]],
) -> None:
    stop_event = asyncio.Event()
    reader = _FakeStreamReader(empty_batches, stop_event)
    sink = _FakeFillSink()
    consumer = FillIngestionConsumer(reader, sink, STREAM, GROUP, CONSUMER)

    count = await consumer.process_once()

    assert count == 0
