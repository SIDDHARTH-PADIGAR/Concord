"""Unit tests for seed_demo_data using plain fakes -- no Redis, no database."""

from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.simulation.demo_seeder import seed_demo_data
from concord_core.simulation.market_data_simulator import SimulatedFillHistory

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
STREAM = "fills"
GROUP = "fill-workers"


def _fill(execution_id: str) -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=AAPL,
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150"),
        executed_at=T0,
        status=TradeStatus.NEW,
    )


class _FakeInternalFillPublisher:
    def __init__(self) -> None:
        self.ensure_consumer_group_calls: list[tuple[str, str]] = []
        self.published: list[tuple[str, Fill]] = []

    async def ensure_consumer_group(self, stream: str, group: str) -> None:
        self.ensure_consumer_group_calls.append((stream, group))

    async def publish(self, stream: str, fill: Fill) -> str:
        self.published.append((stream, fill))
        return f"msg-{len(self.published)}"


class _FakeStreetFillSink:
    def __init__(self) -> None:
        self.inserted: list[Fill] = []

    async def insert_fill(self, fill: Fill) -> bool:
        self.inserted.append(fill)
        return True


async def test_publishes_internal_fills_and_inserts_street_fills() -> None:
    history = SimulatedFillHistory(
        instrument=AAPL,
        internal_fills=[_fill("EX-1"), _fill("EX-2")],
        street_fills=[_fill("EX-1")],
    )
    publisher = _FakeInternalFillPublisher()
    sink = _FakeStreetFillSink()

    await seed_demo_data(history, publisher, sink, STREAM, GROUP)

    assert [fill for _, fill in publisher.published] == history.internal_fills
    assert sink.inserted == history.street_fills


async def test_ensures_consumer_group_before_publishing() -> None:
    history = SimulatedFillHistory(instrument=AAPL, internal_fills=[_fill("EX-1")], street_fills=[])
    publisher = _FakeInternalFillPublisher()
    sink = _FakeStreetFillSink()

    await seed_demo_data(history, publisher, sink, STREAM, GROUP)

    assert publisher.ensure_consumer_group_calls == [(STREAM, GROUP)]


async def test_empty_history_publishes_and_inserts_nothing() -> None:
    history = SimulatedFillHistory(instrument=AAPL, internal_fills=[], street_fills=[])
    publisher = _FakeInternalFillPublisher()
    sink = _FakeStreetFillSink()

    await seed_demo_data(history, publisher, sink, STREAM, GROUP)

    assert publisher.published == []
    assert sink.inserted == []
