"""Orchestrates computing and persisting Positions from Fill history."""

from typing import Protocol

from concord_core.domain.entities import Fill
from concord_core.domain.position import Position, build_position
from concord_core.domain.value_objects import Instrument


class FillSource(Protocol):
    async def get_by_instrument(self, instrument: Instrument) -> list[Fill]: ...


class SnapshotSink(Protocol):
    async def insert_snapshot(self, position: Position) -> None: ...


class PositionService:
    """Depends on the minimal Protocols it needs, not concrete repository
    classes -- FillRepository and PositionSnapshotRepository satisfy
    these structurally, but so does any test fake with matching methods.
    """

    def __init__(self, fills: FillSource, snapshots: SnapshotSink) -> None:
        self._fills = fills
        self._snapshots = snapshots

    async def compute_position(self, instrument: Instrument) -> Position | None:
        """Full replay of the instrument's fill history. Returns None if
        the instrument has never traded -- distinct from a zero position.
        """
        fills = await self._fills.get_by_instrument(instrument)
        if not fills:
            return None
        return build_position(fills)

    async def compute_and_snapshot(self, instrument: Instrument) -> Position | None:
        position = await self.compute_position(instrument)
        if position is not None:
            await self._snapshots.insert_snapshot(position)
        return position
