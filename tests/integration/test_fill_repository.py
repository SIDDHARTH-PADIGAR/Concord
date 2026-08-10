"""Integration tests for FillRepository against a live TimescaleDB instance.

Requires infra/docker-compose.yml running locally, or the timescaledb
service container CI provides. Excluded from default `pytest` runs --
see the `integration` marker registered in pyproject.toml.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.domain.entities import Fill
from concord_core.domain.enums import InstrumentType, Side, TradeStatus
from concord_core.domain.value_objects import Instrument
from concord_core.storage.database import apply_migrations, create_pool
from concord_core.storage.fill_repository import FillRepository

MIGRATIONS_DIR = Path(__file__).parents[2] / "infra" / "sql"

pytestmark = pytest.mark.integration


def _sample_fill(execution_id: str = "EX-1") -> Fill:
    return Fill(
        exchange_execution_id=execution_id,
        trade_id="TR-1",
        instrument=Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY),
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150.25"),
        executed_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC),
        status=TradeStatus.NEW,
    )


@pytest.fixture
async def repository():
    settings = DatabaseSettings()
    pool = await create_pool(settings)
    await apply_migrations(pool, MIGRATIONS_DIR)
    yield FillRepository(pool)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE fills")
    await pool.close()


async def test_insert_fill_returns_true_for_new_fill(repository: FillRepository) -> None:
    assert await repository.insert_fill(_sample_fill()) is True


async def test_insert_fill_returns_false_for_duplicate_delivery(
    repository: FillRepository,
) -> None:
    fill = _sample_fill()
    await repository.insert_fill(fill)
    assert await repository.insert_fill(fill) is False


async def test_get_by_execution_id_round_trips_fill(repository: FillRepository) -> None:
    fill = _sample_fill()
    await repository.insert_fill(fill)
    fetched = await repository.get_by_execution_id(fill.exchange_execution_id)
    assert fetched == fill


async def test_get_by_execution_id_returns_none_when_missing(
    repository: FillRepository,
) -> None:
    assert await repository.get_by_execution_id("does-not-exist") is None


async def test_get_by_trade_id_returns_all_fills_ordered_by_execution_time(
    repository: FillRepository,
) -> None:
    early = _sample_fill("EX-1")
    late = _sample_fill("EX-2").model_copy(
        update={"executed_at": datetime(2026, 8, 5, 13, 0, 0, tzinfo=UTC)}
    )
    await repository.insert_fill(late)
    await repository.insert_fill(early)

    fills = await repository.get_by_trade_id("TR-1")

    assert [f.exchange_execution_id for f in fills] == ["EX-1", "EX-2"]


async def test_get_by_instrument_returns_all_fills_ordered_by_execution_time(
    repository: FillRepository,
) -> None:
    early = _sample_fill("EX-1")
    late = _sample_fill("EX-2").model_copy(
        update={"executed_at": datetime(2026, 8, 5, 13, 0, 0, tzinfo=UTC)}
    )
    await repository.insert_fill(late)
    await repository.insert_fill(early)

    fills = await repository.get_by_instrument(early.instrument)

    assert [f.exchange_execution_id for f in fills] == ["EX-1", "EX-2"]


async def test_get_distinct_instruments_returns_each_traded_instrument_once(
    repository: FillRepository,
) -> None:
    await repository.insert_fill(_sample_fill("EX-1"))
    await repository.insert_fill(_sample_fill("EX-2"))  # same instrument, different fill

    instruments = await repository.get_distinct_instruments()

    assert instruments == [Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)]


async def test_get_distinct_instruments_returns_empty_list_when_no_fills(
    repository: FillRepository,
) -> None:
    assert await repository.get_distinct_instruments() == []
