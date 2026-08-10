"""Seeds paired internal/street fill histories into real infrastructure for
manual demos and testing.

Internal fills are published onto the Redis fills stream -- the same
path the real Async Gateway (not yet built) will eventually use, so a
running concord-worker consumes them exactly as it would in production.
Street fills are inserted directly into street-side storage, since no
street ingestion service exists yet (see docs/architecture.md, Deferred
Extension Points).
"""

from typing import Protocol

from concord_core.domain.entities import Fill
from concord_core.simulation.market_data_simulator import SimulatedFillHistory


class InternalFillPublisher(Protocol):
    async def ensure_consumer_group(self, stream: str, group: str) -> None: ...

    async def publish(self, stream: str, fill: Fill) -> str: ...


class StreetFillSink(Protocol):
    async def insert_fill(self, fill: Fill) -> bool: ...


async def seed_demo_data(
    history: SimulatedFillHistory,
    internal_publisher: InternalFillPublisher,
    street_sink: StreetFillSink,
    stream: str,
    group: str,
) -> None:
    """Publishes internal_fills onto the given Redis stream and inserts
    street_fills directly into street storage. Ensures the consumer
    group exists first, so publishing never races a worker's own
    group-creation on startup.
    """
    await internal_publisher.ensure_consumer_group(stream, group)
    for fill in history.internal_fills:
        await internal_publisher.publish(stream, fill)
    for fill in history.street_fills:
        await street_sink.insert_fill(fill)
