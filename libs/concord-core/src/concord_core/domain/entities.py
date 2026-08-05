"""Core domain entities: Trade and Fill.

Both are immutable (frozen). Under Concord's event-sourcing model
(docs/architecture.md, Decision 3), a correction or cancellation is
never a mutation of an existing record -- it is a new Fill event that
references the original via `corrects_execution_id`.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from concord_core.domain.enums import Side, TradeStatus
from concord_core.domain.value_objects import Instrument


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware, got naive datetime")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"timestamp must be UTC, got offset {value.utcoffset()}")
    return value


class Trade(BaseModel):
    """The order-level aggregate identity that one or more Fills execute against.

    Holds no list of child Fills -- that relationship is queried from
    the Fill event log (grouped by `trade_id`), not stored here.
    Storing it here would duplicate the event log and risk drifting
    out of sync with it.
    """

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1)
    instrument: Instrument
    side: Side
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class Fill(BaseModel):
    """An immutable execution event reported by the street/exchange."""

    model_config = ConfigDict(frozen=True)

    exchange_execution_id: str = Field(min_length=1)
    trade_id: str = Field(min_length=1)
    instrument: Instrument
    side: Side
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    executed_at: datetime
    status: TradeStatus
    corrects_execution_id: str | None = None

    @field_validator("executed_at")
    @classmethod
    def _executed_at_is_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def _corrects_execution_id_matches_status(self) -> "Fill":
        if self.status == TradeStatus.NEW:
            if self.corrects_execution_id is not None:
                raise ValueError("a NEW fill must not set corrects_execution_id")
        else:
            if self.corrects_execution_id is None:
                raise ValueError(f"a {self.status} fill must set corrects_execution_id")
            if self.corrects_execution_id == self.exchange_execution_id:
                raise ValueError("a fill cannot correct itself")
        return self
