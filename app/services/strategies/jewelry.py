"""Jewelry planning strategy."""

from __future__ import annotations

from typing import Optional

from ...schemas import JewelrySpec, Report, ReportExtras
from ..palette import PaletteReading
from .base import CatalogEntry, PlanningLine, PlanningStrategy

# Budget-share weights per occasion; allocator normalizes to the actual budget.
_OCCASION_WEIGHTS: dict[str, dict[str, float]] = {
    "wedding": {"necklace": 0.45, "earrings": 0.30, "bracelet": 0.15, "ring": 0.10},
    "festival": {"necklace": 0.35, "earrings": 0.30, "bracelet": 0.20, "ring": 0.15},
    "birthday": {"necklace": 0.25, "earrings": 0.35, "bracelet": 0.20, "ring": 0.20},
    "cocktail": {"necklace": 0.30, "earrings": 0.25, "bracelet": 0.20, "ring": 0.25},
    "everyday": {"necklace": 0.20, "earrings": 0.30, "bracelet": 0.30, "ring": 0.20},
}

_ITEM_TEMPLATES: dict[str, tuple[str, str]] = {
    "necklace": ("Layered pendant set", "Statement chain with pendant; pairs with both ethnic and western necklines."),
    "earrings": ("Chandelier jhumkas", "Drop earrings with stone work; lightweight enough for long wear."),
    "bracelet": ("Filigree kada", "Openable bangle with fine filigree; stacks well with a watch."),
    "ring": ("Cocktail statement ring", "Adjustable band with a solitaire-style stone."),
}


class JewelryStrategy(PlanningStrategy):
    kind = "jewelry"

    def __init__(self) -> None:
        self._outfit: Optional[PaletteReading] = None

    def attach_outfit(self, reading: Optional[PaletteReading]) -> None:
        """Engine calls this when an outfit photo was analyzed successfully."""
        self._outfit = reading

    def desired_lines(self, spec: JewelrySpec) -> list[PlanningLine]:
        weights = _OCCASION_WEIGHTS.get(spec.occasion.value, _OCCASION_WEIGHTS["everyday"])
        style = self._outfit.style if self._outfit else (spec.style_preference[:60] or "Indo-Western")

        lines = []
        # Each piece's nominal price is its occasion weight applied to the
        # full budget; the allocator then scales the whole set onto the
        # spendable amount, preserving the intended proportions.
        for item_type, weight in weights.items():
            name, desc = _ITEM_TEMPLATES[item_type]
            lines.append(
                PlanningLine(
                    category=item_type.capitalize(),
                    role="any",
                    entry=CatalogEntry(
                        name=name,
                        description=desc,
                        unit_price=round(weight * spec.budget, 2),
                        search_terms=f"{spec.occasion.value} {style} {item_type} set",
                    ),
                    quantity=1,
                )
            )
        return lines

    def extras(self, spec: JewelrySpec) -> ReportExtras:
        return ReportExtras(outfit=self._outfit.as_dict() if self._outfit else None)

    def insights(self, spec: JewelrySpec, report: Report) -> list[str]:
        colors = self._outfit.colors if self._outfit else ["gold"]
        style = self._outfit.style if self._outfit else (spec.style_preference[:60] or "classic")
        return [
            f"Outfit palette leads with {colors[0].lower()} - warm gold finishes flatter it most.",
            "Balance is deliberate: a statement necklace pairs with quieter earrings, and vice versa.",
            f"For a {spec.occasion.value} setting, keep ring weight low so it doesn't catch on fabric.",
            f"Hallmark-certified pieces in the {style.lower()} idiom hold resale value better.",
        ]
