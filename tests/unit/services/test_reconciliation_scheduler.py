"""Unit tests for ReconciliationScheduler using plain fakes -- no database."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from concord_core.domain.breaks import BreakEvent, BreakStatus
from concord_core.domain.enums import InstrumentType
from concord_core.domain.value_objects import Instrument
from concord_core.services.reconciliation_scheduler import ReconciliationScheduler

AAPL = Instrument(symbol="AAPL", instrument_type=InstrumentType.EQUITY)
MSFT = Instrument(symbol="MSFT", instrument_type=InstrumentType.EQUITY)
T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


class _FakeInstrumentSource:
    def __init__(self, instruments: list[Instrument]) -> None:
        self._instruments = instruments

    async def get_distinct_instruments(self) -> list[Instrument]:
        return self._instruments


class _FakeReconciler:
    def __init__(
        self,
        results: dict[Instrument, BreakEvent | None],
        on_call: Callable[[], None] | None = None,
    ) -> None:
        self._results = results
        self._on_call = on_call
        self.calls: list[Instrument] = []

    async def reconcile_instrument(self, instrument: Instrument) -> BreakEvent | None:
        self.calls.append(instrument)
        if self._on_call is not None:
            self._on_call()
        return self._results.get(instrument)


def _break_event(instrument: Instrument) -> BreakEvent:
    return BreakEvent(
        break_id="BRK-1",
        instrument=instrument,
        status=BreakStatus.RAISED,
        difference=Decimal("10"),
        detected_at=T0,
    )


class TestRunPass:
    async def test_dedupes_instruments_across_multiple_sources(self) -> None:
        source_a = _FakeInstrumentSource([AAPL])
        source_b = _FakeInstrumentSource([AAPL, MSFT])
        reconciler = _FakeReconciler({AAPL: None, MSFT: None})
        scheduler = ReconciliationScheduler(reconciler, [source_a, source_b])

        await scheduler.run_pass()

        assert reconciler.calls == [AAPL, MSFT]

    async def test_returns_only_emitted_events(self) -> None:
        source = _FakeInstrumentSource([AAPL, MSFT])
        reconciler = _FakeReconciler({AAPL: _break_event(AAPL), MSFT: None})
        scheduler = ReconciliationScheduler(reconciler, [source])

        events = await scheduler.run_pass()

        assert events == [reconciler._results[AAPL]]

    async def test_no_instruments_produces_no_calls(self) -> None:
        source = _FakeInstrumentSource([])
        reconciler = _FakeReconciler({})
        scheduler = ReconciliationScheduler(reconciler, [source])

        events = await scheduler.run_pass()

        assert events == []
        assert reconciler.calls == []


class TestRunForever:
    async def test_stops_immediately_when_stop_event_is_set_during_a_pass(self) -> None:
        stop_event = asyncio.Event()
        source = _FakeInstrumentSource([AAPL])
        reconciler = _FakeReconciler({AAPL: None}, on_call=stop_event.set)
        scheduler = ReconciliationScheduler(reconciler, [source])

        await asyncio.wait_for(scheduler.run_forever(stop_event, interval_seconds=100), timeout=2.0)

        assert reconciler.calls == [AAPL]

    async def test_runs_another_pass_after_the_interval_elapses(self) -> None:
        stop_event = asyncio.Event()
        source = _FakeInstrumentSource([AAPL])
        call_count = 0

        def _on_call() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop_event.set()

        reconciler = _FakeReconciler({AAPL: None}, on_call=_on_call)
        scheduler = ReconciliationScheduler(reconciler, [source])

        await asyncio.wait_for(
            scheduler.run_forever(stop_event, interval_seconds=0.01), timeout=2.0
        )

        assert call_count == 2
