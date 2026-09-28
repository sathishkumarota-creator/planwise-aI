"""Planning engine: the one pipeline every plan goes through.

Order of operations per request:
  1. build the kind-specific prompt from the validated spec
  2. ask the AI client (if configured) for a JSON plan
  3. sanitize whatever came back - clamp prices to the budget, recompute the
     calculation table and remaining amount, ignore malformed categories
  4. if AI output is unusable, run the catalog strategy instead

The original trusted AI JSON if a single top-level key existed; hallucinated
totals and over-budget allocations flowed straight into saved history.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import get_settings
from ..schemas import (
    CategoryAllocation,
    CalculationRow,
    EventSpec,
    HomeSpec,
    ItemRecommendation,
    JewelrySpec,
    Report,
    ReportExtras,
)
from ..uploads import resolve_upload_path
from .ai_client import AiPlanner, NullAiPlanner
from .marketplace import marketplace_links
from .palette import analyze as analyze_palette
from .strategies import STRATEGIES, build_report

logger = logging.getLogger("planwise.engine")

_MAX_CATEGORIES = 12
_MAX_ITEMS_PER_CATEGORY = 10


def create_plan(kind: str, spec: HomeSpec | EventSpec | JewelrySpec, ai: AiPlanner) -> Report:
    strategy = STRATEGIES[kind]

    outfit = None
    if isinstance(spec, JewelrySpec) and spec.outfit_photo_id:
        photo_path = resolve_upload_path(spec.outfit_photo_id)
        if photo_path:
            outfit = analyze_palette(photo_path)
            if kind == "jewelry":
                strategy.attach_outfit(outfit)

    report: Report | None = None
    ai_payload = _request_ai(kind, spec, ai)
    if ai_payload:
        report = _sanitize_ai_report(kind, spec, ai_payload)
        if report is None:
            logger.info("AI payload failed sanitization for kind=%s; using catalog", kind)

    if report is None:
        report = build_report(strategy, spec, spec.budget, get_settings().reserve_ratio)

    if outfit and kind == "jewelry":
        report.extras.outfit = outfit.as_dict()
    return report


# ------------------------------------------------------------------ prompts


def _request_ai(kind: str, spec, ai: AiPlanner) -> Optional[dict]:
    prompt = _PROMPT_BUILDERS[kind](spec)
    image_path = None
    if isinstance(spec, JewelrySpec) and spec.outfit_photo_id:
        photo_path = resolve_upload_path(spec.outfit_photo_id)
        image_path = str(photo_path) if photo_path else None
    return ai.complete_json(prompt, image_path) if not isinstance(ai, NullAiPlanner) else None


def _home_prompt(spec: HomeSpec) -> str:
    rooms = ", ".join(room.value.replace("_", " ") for room in spec.rooms) or "general interiors"
    return f"""
Plan interior purchases for a home in India. Total budget: INR {spec.budget:.0f}.
Items wanted: {spec.light_count} lights, {spec.fan_count} ceiling fans, \
{spec.furniture_count} furniture pieces, {spec.dining_table_count} dining tables.
Rooms in scope: {rooms}. Preferences: {spec.notes or "none"}.

Reply with ONLY a JSON object:
{{
  "categories": [
    {{"name": "Lighting", "items": [
      {{"name": "...", "description": "...", "unit_price": 0, "quantity": 1, "search_terms": "..."}}
    ]}}
  ],
  "insights": ["short actionable tip", "..."]
}}
Prices must be INR and the total must not exceed the budget. 2-4 categories, 1-3 items each.
""".strip()


def _event_prompt(spec: EventSpec) -> str:
    return f"""
Plan an event in India. Total budget: INR {spec.budget:.0f}.
Event type: {spec.event_type}. Guests: {spec.guest_count}. Venue: {spec.venue.value}.
Catering: {"yes" if spec.include_catering else "no"}; decor: {"yes" if spec.include_decor else "no"}; \
entertainment: {"yes" if spec.include_entertainment else "no"}. Preferences: {spec.notes or "none"}.

Reply with ONLY a JSON object:
{{
  "categories": [
    {{"name": "Catering", "items": [
      {{"name": "...", "description": "...", "unit_price": 0, "quantity": 1, "search_terms": "..."}}
    ]}}
  ],
  "venues": [{{"name": "...", "capacity": {spec.guest_count}, "estimated_cost": 0, "search_terms": "..."}}],
  "insights": ["short actionable tip", "..."]
}}
Prices must be INR and the total must not exceed the budget. 3-5 categories, 1-3 items each.
""".strip()


def _jewelry_prompt(spec: JewelrySpec) -> str:
    return f"""
Recommend jewelry for an outfit in India. Total budget: INR {spec.budget:.0f}.
Occasion: {spec.occasion.value}. Style preference: {spec.style_preference or "unspecified"}.
{("An outfit photo is attached; match colors and formality." if spec.outfit_photo_id else "")}

Reply with ONLY a JSON object:
{{
  "categories": [
    {{"name": "Necklace", "items": [
      {{"name": "...", "description": "...", "unit_price": 0, "quantity": 1, "search_terms": "..."}}
    ]}}
  ],
  "outfit": {{"colors": ["..."], "style": "...", "formality": "..."}},
  "insights": ["short styling tip", "..."]
}}
Prices must be INR and the total must not exceed the budget. 3-4 categories, one item each.
""".strip()


_PROMPT_BUILDERS = {"home": _home_prompt, "event": _event_prompt, "jewelry": _jewelry_prompt}


# ------------------------------------------------------------------ sanitizer


def _sanitize_ai_report(kind: str, spec, payload: dict) -> Optional[Report]:
    """Coerce AI output into the report envelope; None if it is unusable."""
    raw_categories = payload.get("categories")
    if not isinstance(raw_categories, list) or not raw_categories:
        return None

    budget = float(spec.budget)
    categories: list[CategoryAllocation] = []
    seen_names: set[str] = set()
    for raw_cat in raw_categories[:_MAX_CATEGORIES]:
        if not isinstance(raw_cat, dict):
            continue
        name = str(raw_cat.get("name", "")).strip()[:40] or "General"
        if name.lower() in seen_names:
            continue
        items: list[ItemRecommendation] = []
        for raw_item in (raw_cat.get("items") or [])[:_MAX_ITEMS_PER_CATEGORY]:
            if not isinstance(raw_item, dict):
                continue
            try:
                unit_price = round(max(0.0, float(raw_item.get("unit_price", 0))), 2)
                quantity = max(1, int(raw_item.get("quantity", 1)))
            except (TypeError, ValueError):
                continue
            items.append(
                ItemRecommendation(
                    name=str(raw_item.get("name", "")).strip()[:80] or "Recommended item",
                    description=str(raw_item.get("description", "")).strip()[:300],
                    unit_price=unit_price,
                    quantity=quantity,
                    search_terms=str(raw_item.get("search_terms", "")).strip()[:120],
                    marketplaces={},
                )
            )
        if not items:
            continue
        amount = round(sum(i.unit_price * i.quantity for i in items), 2)
        categories.append(CategoryAllocation(name=name, amount=amount, items=items))
        seen_names.add(name.lower())

    if not categories:
        return None

    # Re-derive totals from the sanitized items; never trust AI arithmetic.
    planned_total = round(sum(cat.amount for cat in categories), 2)
    if planned_total > budget:
        scale = (budget * 0.95) / planned_total
        for cat in categories:
            cat.amount = round(cat.amount * scale, 2)
            for item in cat.items:
                item.unit_price = round(cat.amount / item.quantity, 2)
        planned_total = round(sum(cat.amount for cat in categories), 2)

    for cat in categories:
        role = _role_guess(kind, cat.name)
        for item in cat.items:
            query = item.search_terms or item.name
            item.marketplaces = marketplace_links(kind, role, query)

    calculation = [
        CalculationRow(
            category=cat.name,
            units=sum(i.quantity for i in cat.items),
            cost=cat.amount,
            budget_share=round(cat.amount / budget * 100, 1),
        )
        for cat in categories
    ]

    insights = [
        str(tip).strip()[:200]
        for tip in (payload.get("insights") or [])
        if isinstance(tip, (str, int, float))
    ][:6]

    extras = _sanitize_extras(kind, payload)

    return Report(
        kind=kind,  # type: ignore[arg-type]
        budget=budget,
        reserve=round(max(budget - planned_total, 0.0), 2),
        source="gemini",
        categories=categories,
        calculation=calculation,
        insights=insights,
        extras=extras,
    )


def _sanitize_extras(kind: str, payload: dict) -> ReportExtras:
    extras = ReportExtras()
    if kind == "event" and isinstance(payload.get("venues"), list):
        extras.venues = [
            {
                "name": str(v.get("name", "")).strip()[:80],
                "capacity": int(v.get("capacity", 0) or 0),
                "estimated_cost": round(max(0.0, float(v.get("estimated_cost", 0) or 0)), 2),
                "search_terms": str(v.get("search_terms", "")).strip()[:120],
            }
            for v in payload["venues"][:5]
            if isinstance(v, dict) and v.get("name")
        ]
        for venue in extras.venues:
            venue["search_links"] = marketplace_links("event", "venue", venue["search_terms"] or venue["name"])
    if kind == "jewelry" and isinstance(payload.get("outfit"), dict):
        raw_outfit = payload["outfit"]
        extras.outfit = {
            "colors": [str(c)[:30] for c in (raw_outfit.get("colors") or [])[:4] if c],
            "style": str(raw_outfit.get("style", "")).strip()[:60],
            "formality": str(raw_outfit.get("formality", "")).strip()[:40],
        }
    return extras


def _role_guess(kind: str, category_name: str) -> str:
    name = category_name.lower()
    if kind == "event":
        if any(w in name for w in ("venue", "hall", "stay")):
            return "venue"
        if any(w in name for w in ("cater", "food", "cake", "drink")):
            return "food"
        if any(w in name for w in ("decor", "flower", "balloon", "light")):
            return "decor"
        if any(w in name for w in ("entertain", "music", "game", "photo")):
            return "entertainment"
    return "any"
