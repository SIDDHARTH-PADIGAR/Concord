"""Tests for RedisStreamClient against fakeredis (no live Redis required)."""

from datetime import UTC, datetime
from decimal import Decimal

import fakeredis.aioredis
import pytest

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.messaging.redis_streams import RedisStreamClient

STREAM = "fills"
GROUP = "workers"


def _sample_fill() -> Fill:
    return Fill(
        exchange_execution_id="EX-1",
        trade_id="TR-1",
        instrument=Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY),
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150.25"),
        executed_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC),
        status=TradeStatus.NEW,
    )


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_publish_then_read_round_trips_fill(redis_client) -> None:
    stream_client = RedisStreamClient(redis_client)
    fill = _sample_fill()
    await stream_client.ensure_consumer_group(STREAM, GROUP)

    published_id = await stream_client.publish(STREAM, fill)
    messages = await stream_client.read(STREAM, GROUP, "worker-1", count=10, block_ms=100)

    assert len(messages) == 1
    read_id, read_fill = messages[0]
    assert read_id == published_id
    assert read_fill == fill


async def test_ack_clears_pending_entry(redis_client) -> None:
    stream_client = RedisStreamClient(redis_client)
    await stream_client.ensure_consumer_group(STREAM, GROUP)
    message_id = await stream_client.publish(STREAM, _sample_fill())
    await stream_client.read(STREAM, GROUP, "worker-1", count=10, block_ms=100)

    pending_before = await redis_client.xpending(STREAM, GROUP)
    assert pending_before["pending"] == 1

    await stream_client.ack(STREAM, GROUP, message_id)

    pending_after = await redis_client.xpending(STREAM, GROUP)
    assert pending_after["pending"] == 0


async def test_ensure_consumer_group_is_idempotent(redis_client) -> None:
    stream_client = RedisStreamClient(redis_client)
    await stream_client.ensure_consumer_group(STREAM, GROUP)
    await stream_client.ensure_consumer_group(STREAM, GROUP)  # must not raise


async def test_read_with_no_messages_returns_empty_list(redis_client) -> None:
    stream_client = RedisStreamClient(redis_client)
    await stream_client.ensure_consumer_group(STREAM, GROUP)
    messages = await stream_client.read(STREAM, GROUP, "worker-1", count=10, block_ms=100)
    assert messages == []
