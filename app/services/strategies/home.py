"""Home interior planning strategy."""

from __future__ import annotations

from ...schemas import HomeSpec, Report
from .base import CatalogEntry, PlanningLine, PlanningStrategy


class HomeStrategy(PlanningStrategy):
    kind = "home"

    _LIGHTS = CatalogEntry(
        name="Warm-white LED ceiling fixtures",
        description="Energy-efficient ambient lighting; prefer 12W panels for living areas.",
        unit_price=850.0,
        search_terms="LED ceiling light panel warm white",
    )
    _FANS = CatalogEntry(
        name="BLDC energy-saving ceiling fan",
        description="Silent high-airflow fan with remote; 5-star rated to cut running cost.",
        unit_price=2400.0,
        search_terms="BLDC ceiling fan energy saving remote",
    )
    _FURNITURE = CatalogEntry(
        name="Compact accent seating / storage unit",
        description="Solid-wood framed piece suited to apartment living rooms.",
        unit_price=11500.0,
        search_terms="solid wood accent chair storage unit apartment",
    )
    _DINING = CatalogEntry(
        name="Four-seater dining table",
        description="Engineered-wood minimalist dining set for daily use.",
        unit_price=14000.0,
        search_terms="4 seater dining table wooden compact",
    )

    def desired_lines(self, spec: HomeSpec) -> list[PlanningLine]:
        return [
            PlanningLine("Lighting", "any", self._LIGHTS, spec.light_count),
            PlanningLine("Ceiling Fans", "any", self._FANS, spec.fan_count),
            PlanningLine("Furniture", "any", self._FURNITURE, spec.furniture_count),
            PlanningLine("Dining", "any", self._DINING, spec.dining_table_count),
        ]

    @staticmethod
    def _room_names(spec: HomeSpec) -> str:
        return " and ".join(room.value.replace("_", " ") for room in spec.rooms) or "the whole home"

    def insights(self, spec: HomeSpec, report: Report) -> list[str]:
        tips = [
            f"Plan covers {self._room_names(spec)}; buy lighting and fans together during festive sales - fixture bundles often save 10-15%.",
            "BLDC fans cost more upfront but typically repay the difference in electricity savings within two years.",
        ]
        if spec.notes:
            tips.append(f"Noted preference taken into account: {spec.notes.strip()[:140]}")
        if report.reserve > 0:
            tips.append(f"₹{report.reserve:,.0f} held back as reserve for delivery, installation, and small fittings.")
        if spec.dining_table_count and spec.furniture_count:
            tips.append("Measure the dining area before ordering - a 4-seater needs roughly a 90x150 cm footprint.")
        return tips
