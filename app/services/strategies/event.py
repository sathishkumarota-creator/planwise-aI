"""Event (party) planning strategy."""

from __future__ import annotations

from ...schemas import EventSpec, Report, ReportExtras, VenueKind
from ..marketplace import marketplace_links
from .base import CatalogEntry, PlanningLine, PlanningStrategy


class EventStrategy(PlanningStrategy):
    kind = "event"

    _CATERING = CatalogEntry(
        name="Party catering platter",
        description="Starters, mains, and dessert service per guest.",
        unit_price=380.0,
        search_terms="party food catering platter bulk order",
    )
    _VENUE = CatalogEntry(
        name="Event venue booking",
        description="Half-day slot sized to the guest list.",
        unit_price=9000.0,
        search_terms="event venue half day booking",
    )
    _DECOR = CatalogEntry(
        name="Theme decoration kit",
        description="Balloon arch, backdrop, fairy lights, and banner set.",
        unit_price=2200.0,
        search_terms="party decoration kit balloons backdrop lights",
    )
    _ENTERTAINMENT = CatalogEntry(
        name="Music and games package",
        description="Speaker rental plus curated playlist and group games.",
        unit_price=2500.0,
        search_terms="bluetooth speaker rental party games",
    )
    _CONTINGENCY = CatalogEntry(
        name="Contingency buffer",
        description="Extra disposables, ice, drinks, and last-minute additions.",
        unit_price=1200.0,
        search_terms="disposable tableware cups napkins bulk",
    )

    def desired_lines(self, spec: EventSpec) -> list[PlanningLine]:
        lines: list[PlanningLine] = []
        if spec.venue != VenueKind.HOME:
            venue_entry = CatalogEntry(
                name=f"{spec.venue.value.replace('_', ' ').title()} booking",
                description=self._VENUE.description,
                unit_price=self._VENUE.unit_price,
                search_terms=f"{spec.venue.value.replace('_', ' ')} venue for {spec.event_type.lower()}",
            )
            lines.append(PlanningLine("Venue", "venue", venue_entry, 1))
        if spec.include_catering:
            lines.append(PlanningLine("Catering", "food", self._CATERING, spec.guest_count))
        if spec.include_decor:
            lines.append(PlanningLine("Decoration", "decor", self._DECOR, 1))
        if spec.include_entertainment:
            lines.append(PlanningLine("Entertainment", "entertainment", self._ENTERTAINMENT, 1))
        lines.append(PlanningLine("Contingency", "any", self._CONTINGENCY, 1))
        return lines

    def extras(self, spec: EventSpec) -> ReportExtras:
        if spec.venue == VenueKind.HOME:
            return ReportExtras()
        label = spec.venue.value.replace("_", " ")
        base_query = f"{label} venue for {spec.event_type.lower()}"
        links = marketplace_links("event", "venue", base_query)
        venues = [
            {
                "name": f"Mid-range {label} ({spec.guest_count} guests)",
                "capacity": spec.guest_count,
                "estimated_cost": round(self._VENUE.unit_price * 0.8, 2),
                "search_terms": base_query,
                "search_links": links,
            },
            {
                "name": f"Premium {label} package",
                "capacity": int(spec.guest_count * 1.25),
                "estimated_cost": round(self._VENUE.unit_price * 1.4, 2),
                "search_terms": f"premium {base_query}",
                "search_links": links,
            },
        ]
        return ReportExtras(venues=venues)

    def insights(self, spec: EventSpec, report: Report) -> list[str]:
        tips = [
            f"Per-guest spend works out to ₹{(report.planned_total / spec.guest_count):,.0f}; order catering 48 hours ahead for bulk rates.",
            "Keep the contingency line for extra guests and disposables rather than upgrading the menu.",
        ]
        if spec.venue == VenueKind.OUTDOOR:
            tips.append("Outdoor venues need a weather fallback - check for an indoor option or canopy rental.")
        if spec.guest_count > 120:
            tips.append("Above 120 guests, buffet counters serve faster than plated service and cost less per head.")
        return tips
