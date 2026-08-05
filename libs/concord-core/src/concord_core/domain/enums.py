"""Core domain enumerations.

These are the smallest shared vocabulary in the system: every service
that touches a trade, fill, or position agrees on these exact string
values. Using ``enum.StrEnum`` (stdlib, 3.11+) instead of a custom
``class X(str, Enum)`` mixin means:

- Values serialize to JSON and onto Redis Streams as their plain
  string form, with no ``.value`` extraction step to forget.
- ``repr()`` and ``str()`` behave consistently -- the old ``str, Enum``
  mixin pattern had inconsistent formatting behaviour depending on
  Python version, which ``StrEnum`` fixes natively.
- Values stay human-readable in redis-cli / XRANGE output during
  incident response, which an ``IntEnum`` would sacrifice for a
  wire-size saving we don't need at this volume.
"""

from enum import StrEnum


class Side(StrEnum):
    """The direction of a trade from the reporting book's perspective.

    Deliberately does not distinguish short sells or buy-to-covers.
    That's a real distinction in some books, but nothing in Concord's
    current scope (position reconciliation, not margin/short-locate
    tracking) needs it. Add it when a real requirement does, not
    speculatively.
    """

    BUY = "BUY"
    SELL = "SELL"


class InstrumentType(StrEnum):
    """The asset class of the instrument a trade or fill references.

    Scoped to what the Market Data Simulator will actually generate.
    Not an attempt to model every asset class a real firm trades --
    extend this list when a milestone actually needs a new type.
    """

    EQUITY = "EQUITY"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    FX = "FX"


class TradeStatus(StrEnum):
    """The nature of a trade event as reported by the source system.

    Concord is event-sourced (see docs/architecture.md, Decision 3):
    trades are never mutated in place. When an exchange cancels or
    corrects a previously reported trade, that arrives as a *new*
    event referencing the original -- it does not rewrite history.
    This enum tags what kind of event a given record represents, not
    a mutable status field on a long-lived row.
    """

    NEW = "NEW"
    CANCELLED = "CANCELLED"
    CORRECTED = "CORRECTED"
