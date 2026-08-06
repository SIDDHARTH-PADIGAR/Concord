"""Wire serialization between Fill entities and Redis Stream fields.

Assumes the Redis client was constructed with decode_responses=True
(see redis_streams.create_redis_client) -- fields arrive as str, not
bytes. Enforcing that at the connection layer means this module never
has to guess.
"""

from collections.abc import Mapping

from concord_core.domain.entities import Fill

_PAYLOAD_FIELD = "payload"


def fill_to_stream_fields(fill: Fill) -> dict[str, str]:
    return {_PAYLOAD_FIELD: fill.model_dump_json()}


def fill_from_stream_fields(fields: Mapping[str, str]) -> Fill:
    return Fill.model_validate_json(fields[_PAYLOAD_FIELD])
