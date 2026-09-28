"""API contracts.

Every payload the web layer accepts or returns is defined here with explicit
bounds, so invalid input is rejected at the edge instead of leaking into the
planning engine. The report envelope is shared by all three planner kinds,
which lets one template render any plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PlanningKind = Literal["home", "event", "jewelry"]


# ---------------------------------------------------------------- enums


class Room(str, Enum):
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"


class VenueKind(str, Enum):
    HOME = "home"
    BANQUET_HALL = "banquet_hall"
    HOTEL = "hotel"
    OUTDOOR = "outdoor"
    RESTAURANT = "restaurant"


class Occasion(str, Enum):
    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    FESTIVAL = "festival"
    COCKTAIL = "cocktail"
    EVERYDAY = "everyday"


# ---------------------------------------------------------------- planner specs
# Upper bounds exist so a single request can never pin the server with absurd
# loops or overflow the report; the UI never offers more than these anyway.


class HomeSpec(BaseModel):
    kind: Literal["home"] = "home"
    budget: float = Field(gt=0, le=100_000_000)
    light_count: int = Field(default=0, ge=0, le=200)
    fan_count: int = Field(default=0, ge=0, le=100)
    furniture_count: int = Field(default=0, ge=0, le=100)
    dining_table_count: int = Field(default=0, ge=0, le=20)
    rooms: list[Room] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _something_to_plan(self) -> "HomeSpec":
        if not (
            self.light_count
            or self.fan_count
            or self.furniture_count
            or self.dining_table_count
        ):
            raise ValueError("Select at least one item to plan for.")
        return self


class EventSpec(BaseModel):
    kind: Literal["event"] = "event"
    budget: float = Field(gt=0, le=100_000_000)
    guest_count: int = Field(ge=1, le=5000)
    event_type: str = Field(max_length=40)
    venue: VenueKind = VenueKind.HOME
    include_catering: bool = True
    include_decor: bool = True
    include_entertainment: bool = True
    notes: str = Field(default="", max_length=1000)

    @field_validator("event_type", mode="after")
    @classmethod
    def _clean_event_type(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Event type is required.")
        return cleaned


class JewelrySpec(BaseModel):
    kind: Literal["jewelry"] = "jewelry"
    budget: float = Field(gt=0, le=100_000_000)
    occasion: Occasion = Occasion.EVERYDAY
    style_preference: str = Field(default="", max_length=400)
    outfit_photo_id: str | None = None


class PlanRequest(BaseModel):
    """Discriminated union keyed on `spec.kind` - one endpoint serves all planners."""

    spec: HomeSpec | EventSpec | JewelrySpec = Field(discriminator="kind")
    title: str = Field(default="", max_length=120)


# ---------------------------------------------------------------- report envelope


@dataclass
class ItemRecommendation:
    name: str
    description: str
    unit_price: float
    quantity: int
    search_terms: str
    marketplaces: dict[str, str] = field(default_factory=dict)


@dataclass
class CategoryAllocation:
    name: str
    amount: float
    items: list[ItemRecommendation]


@dataclass
class CalculationRow:
    category: str
    units: int
    cost: float
    budget_share: float  # percent of the total budget


@dataclass
class ReportExtras:
    """Kind-specific extras (venues for events, outfit analysis for jewelry)."""

    venues: list[dict[str, Any]] = field(default_factory=list)
    outfit: dict[str, Any] | None = None


@dataclass
class Report:
    """Unified shape for every planner kind."""

    kind: PlanningKind
    budget: float
    reserve: float
    source: Literal["gemini", "catalog"]
    categories: list[CategoryAllocation]
    calculation: list[CalculationRow]
    insights: list[str]
    extras: ReportExtras = field(default_factory=ReportExtras)

    @property
    def planned_total(self) -> float:
        return round(sum(cat.amount for cat in self.categories), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "budget": self.budget,
            "reserve": self.reserve,
            "source": self.source,
            "planned_total": self.planned_total,
            "remaining": round(self.budget - self.reserve - self.planned_total, 2),
            "categories": [
                {
                    "name": cat.name,
                    "amount": cat.amount,
                    "items": [
                        {
                            "name": item.name,
                            "description": item.description,
                            "unit_price": item.unit_price,
                            "quantity": item.quantity,
                            "line_total": round(item.unit_price * item.quantity, 2),
                            "search_terms": item.search_terms,
                            "marketplaces": item.marketplaces,
                        }
                        for item in cat.items
                    ],
                }
                for cat in self.categories
            ],
            "calculation": [
                {
                    "category": row.category,
                    "units": row.units,
                    "cost": row.cost,
                    "budget_share": row.budget_share,
                }
                for row in self.calculation
            ],
            "insights": self.insights,
            "extras": {
                "venues": self.extras.venues,
                "outfit": self.extras.outfit,
            },
        }


# ---------------------------------------------------------------- stored plan


@dataclass
class PlanRecord:
    """One saved plan as stored in (and returned from) the repository."""

    id: str
    username: str
    kind: PlanningKind
    title: str
    spec: dict[str, Any]
    report: dict[str, Any]
    created_at: datetime

    def summary(self) -> "PlanSummary":
        return PlanSummary(
            id=self.id,
            kind=self.kind,
            title=self.title,
            budget=float(self.report.get("budget", 0.0)),
            planned_total=float(self.report.get("planned_total", 0.0)),
            remaining=float(self.report.get("remaining", 0.0)),
            created_at=self.created_at,
        )


@dataclass
class PlanSummary:
    id: str
    kind: PlanningKind
    title: str
    budget: float
    planned_total: float
    remaining: float
    created_at: datetime


# ---------------------------------------------------------------- auth


class RegistrationForm(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=72)  # bcrypt reads 72 bytes max
    display_name: str = Field(default="", max_length=80)

    @field_validator("username")
    @classmethod
    def _username_rules(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isalnum() or not cleaned.isascii():
            raise ValueError("Use letters and numbers only (no spaces or symbols).")
        return cleaned.lower()

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        # Shape check only; the local part of emails can be near-arbitrary.
        local, _, domain = value.strip().partition("@")
        if not local or "." not in domain or " " in value:
            raise ValueError("Enter a valid email address.")
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _password_rules(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password needs at least 8 characters.")
        if value.strip() == value.lower() or value.strip() == value.upper():
            raise ValueError("Mix uppercase and lowercase letters in the password.")
        if not any(ch.isdigit() for ch in value):
            raise ValueError("Include at least one digit in the password.")
        return value


class LoginForm(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserView(BaseModel):
    username: str
    email: str
    display_name: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_inr(amount: float) -> str:
    """Indian-style digit grouping, e.g. 1234567.5 -> '₹12,34,567.50'."""
    negative = amount < 0
    value = abs(round(float(amount), 2))
    whole, _, frac = f"{value:.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{'-' if negative else ''}₹{whole}.{frac}"
