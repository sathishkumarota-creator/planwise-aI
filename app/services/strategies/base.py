"""Strategy interface and the shared allocation algorithm.

The original split budgets by hard-coded percentages (lights 15%, fans 20%,
furniture 35%...) regardless of requested quantities, so 2 lights and 50 lights
received the same amount. Here each strategy declares *desired* purchases with
realistic unit prices; the allocator scales them proportionally into the
spendable budget and reports what was left as reserve.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from ...schemas import (
    CategoryAllocation,
    CalculationRow,
    ItemRecommendation,
    Report,
    ReportExtras,
    PlanningKind,
)


@dataclass(frozen=True)
class CatalogEntry:
    """A typical product the strategy can suggest, with a realistic unit price."""

    name: str
    description: str
    unit_price: float
    search_terms: str


@dataclass(frozen=True)
class PlanningLine:
    """One category of desired purchases for a plan."""

    category: str
    role: str  # marketplace role used to pick vendor links
    entry: CatalogEntry
    quantity: int


class PlanningStrategy(ABC):
    """Per-kind planning logic. Implementations stay request-shape agnostic."""

    kind: ClassVar[PlanningKind]

    @abstractmethod
    def desired_lines(self, spec) -> list[PlanningLine]: ...

    @abstractmethod
    def insights(self, spec, report: Report) -> list[str]: ...

    def extras(self, spec) -> ReportExtras:
        return ReportExtras()


_MAX_UPSCALE = 4.0  # never invent a 10x premium tier; leave the rest as reserve


def allocate(
    budget: float,
    lines: list[PlanningLine],
    reserve_ratio: float,
) -> tuple[list[CategoryAllocation], float]:
    """Scale desired purchases onto the spendable budget.

    Returns the category allocations and the unspent reserve. Quantities are
    never changed - the per-unit price absorbs the scaling, mirroring how real
    shopping behaves (same count, cheaper or pricier tier).
    """
    spendable = budget * (1.0 - reserve_ratio)
    desired_total = sum(line.entry.unit_price * line.quantity for line in lines)
    if desired_total <= 0:
        return [], round(budget, 2)
    scale = spendable / desired_total
    scale = min(scale, _MAX_UPSCALE)

    grouped: dict[str, CategoryAllocation] = {}
    for line in lines:
        if line.quantity <= 0:
            continue
        amount = round(line.entry.unit_price * line.quantity * scale, 2)
        item = ItemRecommendation(
            name=line.entry.name,
            description=line.entry.description,
            unit_price=round(amount / line.quantity, 2),
            quantity=line.quantity,
            search_terms=line.entry.search_terms,
        )
        if line.category in grouped:
            grouped[line.category].items.append(item)
            grouped[line.category].amount = round(grouped[line.category].amount + amount, 2)
        else:
            grouped[line.category] = CategoryAllocation(
                name=line.category, amount=amount, items=[item]
            )

    categories = list(grouped.values())
    reserve = round(budget - sum(cat.amount for cat in categories), 2)
    return categories, max(reserve, 0.0)


def build_report(
    strategy: PlanningStrategy,
    spec,
    budget: float,
    reserve_ratio: float,
    source: str = "catalog",
    extras: ReportExtras | None = None,
) -> Report:
    """Run a strategy end-to-end: allocate, calculate, and decorate with links."""
    from ..marketplace import marketplace_links

    lines = strategy.desired_lines(spec)
    categories, reserve = allocate(budget, lines, reserve_ratio)

    for category in categories:
        for item in category.items:
            item.marketplaces = marketplace_links(strategy.kind, _role_of(category.name, lines), item.search_terms)

    rows = [
        CalculationRow(
            category=cat.name,
            units=sum(i.quantity for i in cat.items),
            cost=cat.amount,
            budget_share=round(cat.amount / budget * 100, 1) if budget else 0.0,
        )
        for cat in categories
    ]

    report = Report(
        kind=strategy.kind,
        budget=budget,
        reserve=reserve,
        source=source,  # type: ignore[arg-type]
        categories=categories,
        calculation=rows,
        insights=[],
        extras=extras or strategy.extras(spec),
    )
    report.insights = strategy.insights(spec, report)
    return report


def _role_of(category_name: str, lines: list[PlanningLine]) -> str:
    for line in lines:
        if line.category == category_name:
            return line.role
    return "any"
