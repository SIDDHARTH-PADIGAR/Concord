"""Concord Core.

Shared domain models, configuration primitives, and cross-cutting
concerns used by every Concord service (gateway, worker, reconciler,
reporter, replay).

This package has no knowledge of any specific service's runtime
behaviour. It exists so that every service imports the *same*
definition of a Trade, a Fill, a Position, and so on -- correctness
of the whole system depends on that being true.
"""

__version__ = "0.1.0"
