"""BreakEvent: an immutable record of a break being raised or resolved.

Mirrors the event-sourced pattern already used for Fill (TradeStatus
tags NEW/CANCELLED/CORRECTED) and Position (never mutated, only
appended). A break's current state is derived by finding its latest
event, not by mutating a status field in place.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from concord_core.domain.temporal import require_utc
from concord_core.domain.value_objects import Instrument


class BreakStatus(StrEnum):
    RAISED = "RAISED"
    RESOLVED = "RESOLVED"


class BreakEvent(BaseModel):
    """break_id correlates a RAISED event with its eventual RESOLVED
    event -- both share the same break_id, distinguishing "the same
    break closing" from "a new, unrelated break opening."
    """

    model_config = ConfigDict(frozen=True)

    break_id: str = Field(min_length=1)
    instrument: Instrument
    status: BreakStatus
    difference: Decimal
    detected_at: datetime

    @field_validator("detected_at")
    @classmethod
    def _detected_at_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)
