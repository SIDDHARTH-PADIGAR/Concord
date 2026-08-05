"""Value objects shared by domain entities."""

from pydantic import BaseModel, ConfigDict, Field

from concord_core.domain.enums import InstrumentType


class Instrument(BaseModel):
    """An immutable, hashable reference to a tradeable instrument."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    instrument_type: InstrumentType
