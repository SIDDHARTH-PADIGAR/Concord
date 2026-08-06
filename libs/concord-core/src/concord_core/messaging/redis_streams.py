"""Async Redis Streams client for publishing and consuming Fill events."""

from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from concord_core.config.settings import RedisSettings
from concord_core.domain.entities import Fill
from concord_core.messaging.serialization import fill_from_stream_fields, fill_to_stream_fields


def create_redis_client(settings: RedisSettings) -> Redis:
    """Construct the one Redis client type this codebase uses.

    decode_responses=True is enforced here, not left to each caller,
    so every downstream module can assume str fields.

    redis-py's `from_url` is untyped internally and returns Any; the
    cast documents that we know the concrete type, not that we've
    silenced a real error.
    """
    client = Redis.from_url(settings.url, decode_responses=True)
    return cast(Redis, client)


class RedisStreamClient:
    """Thin wrapper over XADD/XREADGROUP/XACK, Fill-aware.

    Consumer-group semantics (at-least-once delivery, per-message ack)
    live here once, instead of being reimplemented per service.
    """

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def ensure_consumer_group(self, stream: str, group: str) -> None:
        """Idempotent: safe to call on every worker startup."""
        try:
            await self._redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, stream: str, fill: Fill) -> str:
        fields = fill_to_stream_fields(fill)
        # redis-py's stub types xadd's fields param as an invariant dict
        # over a wide value union; dict[str, str] is structurally fine at
        # runtime but mypy won't accept it without this cast.
        message_id = await self._redis.xadd(stream, cast(dict[Any, Any], fields))
        assert isinstance(message_id, str)
        return message_id

    async def read(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, Fill]]:
        response = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
        if not response:
            return []

        results: list[tuple[str, Fill]] = []
        for _stream_name, messages in response:
            for message_id, fields in messages:
                assert isinstance(message_id, str)
                assert isinstance(fields, dict)
                results.append((message_id, fill_from_stream_fields(fields)))
        return results

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        await self._redis.xack(stream, group, message_id)
