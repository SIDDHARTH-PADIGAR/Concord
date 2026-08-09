"""Position: the net signed quantity held in one instrument, derived from a fill history."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from concord_core.domain.entities import Fill
from concord_core.domain.enums import Side, TradeStatus
from concord_core.domain.temporal import require_utc
from concord_core.domain.value_objects import Instrument


class Position(BaseModel):
    """Never mutated in place -- every change in the underlying fills
    produces a new Position via build_position, consistent with
    Concord's event-sourcing model.
    """

    model_config = ConfigDict(frozen=True)

    instrument: Instrument
    quantity: Decimal
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def _as_of_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


def build_position(fills: Sequence[Fill]) -> Position:
    """Folds a fill history for one instrument into a net Position.

    Correction semantics: a CORRECTED fill replaces its original's
    contribution (by exchange_execution_id) with its own; a CANCELLED
    fill removes its original's contribution entirely. Both must
    reference an original present in `fills` -- this function expects
    a complete fill history for the instrument, not a partial window.
    """
    if not fills:
        raise ValueError("cannot build a position from an empty fill list")

    instruments = {fill.instrument for fill in fills}
    if len(instruments) > 1:
        raise ValueError(
            f"all fills must reference the same instrument, got "
            f"{sorted(i.symbol for i in instruments)}"
        )

    effective: dict[str, Fill] = {
        fill.exchange_execution_id: fill for fill in fills if fill.status == TradeStatus.NEW
    }

    corrections = sorted(
        (fill for fill in fills if fill.status != TradeStatus.NEW),
        key=lambda fill: fill.executed_at,
    )
    for correction in corrections:
        original_id = correction.corrects_execution_id
        assert original_id is not None  # enforced by Fill's own validation
        if original_id not in effective:
            raise ValueError(
                f"fill {correction.exchange_execution_id} ({correction.status}) references "
                f"{original_id}, which is not present in the supplied fill set"
            )
        if correction.status == TradeStatus.CANCELLED:
            del effective[original_id]
        else:
            effective[original_id] = correction

    quantity = sum(
        (fill.quantity if fill.side == Side.BUY else -fill.quantity for fill in effective.values()),
        start=Decimal("0"),
    )
    as_of = max(fill.executed_at for fill in fills)
    instrument = next(iter(instruments))
    return Position(instrument=instrument, quantity=quantity, as_of=as_of)


def build_position_or_none(fills: Sequence[Fill]) -> Position | None:
    """Same as build_position, but returns None instead of raising for
    an empty fill list. Shared by every caller for whom "this
    instrument has no fills yet" is an expected, valid outcome rather
    than a caller error -- PositionService.compute_position and
    StreetPositionSourceAdapter.get_position both rely on this.
    """
    if not fills:
        return None
    return build_position(fills)
