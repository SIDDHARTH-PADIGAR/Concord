"""ReconciliationResult: the outcome of comparing an internal position against a street position."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from concord_core.domain.temporal import require_utc
from concord_core.domain.value_objects import Instrument


class ReconciliationResult(BaseModel):
    """Immutable outcome of one reconciliation comparison for one instrument.

    internal_quantity/street_quantity are None when that side has no
    position at all (the instrument never traded there) -- distinct
    from a real zero position. difference and is_break always treat a
    missing side as zero for the purpose of computing a numeric gap.
    """

    model_config = ConfigDict(frozen=True)

    instrument: Instrument
    internal_quantity: Decimal | None
    street_quantity: Decimal | None
    difference: Decimal
    is_break: bool
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def _as_of_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)
