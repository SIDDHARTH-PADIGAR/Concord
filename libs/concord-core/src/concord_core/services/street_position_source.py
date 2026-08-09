"""Concrete StreetPositionSource, backed by a street-side Fill store.

Resolves the Protocol left deferred in Task 5 -- now that a real
end-to-end reconciliation loop needs it, this adapter folds
street_fills into a Position the same way PositionService folds the
internal side, via the shared build_position_or_none.
"""

from typing import Protocol

from concord_core.domain.entities import Fill
from concord_core.domain.position import Position, build_position_or_none
from concord_core.domain.value_objects import Instrument


class StreetFillSource(Protocol):
    async def get_by_instrument(self, instrument: Instrument) -> list[Fill]: ...


class StreetPositionSourceAdapter:
    """Satisfies ReconciliationService's StreetPositionSource Protocol
    structurally via get_position(). Depends on StreetFillSource, not
    the concrete StreetFillRepository class.
    """

    def __init__(self, fills: StreetFillSource) -> None:
        self._fills = fills

    async def get_position(self, instrument: Instrument) -> Position | None:
        fills = await self._fills.get_by_instrument(instrument)
        return build_position_or_none(fills)
