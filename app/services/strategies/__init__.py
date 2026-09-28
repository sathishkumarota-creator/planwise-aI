"""Registry of planning strategies, keyed by plan kind."""

from __future__ import annotations

from .base import PlanningStrategy, allocate, build_report
from .event import EventStrategy
from .home import HomeStrategy
from .jewelry import JewelryStrategy

STRATEGIES: dict[str, PlanningStrategy] = {
    "home": HomeStrategy(),
    "event": EventStrategy(),
    "jewelry": JewelryStrategy(),
}

__all__ = [
    "STRATEGIES",
    "PlanningStrategy",
    "allocate",
    "build_report",
    "EventStrategy",
    "HomeStrategy",
    "JewelryStrategy",
]
