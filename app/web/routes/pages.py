"""Server-rendered pages: landing, dashboard, planner forms, history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from ...schemas import PlanningKind, PlanSummary
from ...storage import PlanRepository
from ..deps import current_user, require_page_user
from ..templating import get_templates

router = APIRouter()
templates = get_templates()
plan_repo = PlanRepository()

KIND_LABELS: dict[str, str] = {
    "home": "Home interior",
    "event": "Event",
    "jewelry": "Jewelry",
}


@router.get("/")
async def landing(request: Request, user=Depends(current_user)):
    template = "dashboard.html" if user else "landing.html"
    context: dict = {"user": user}
    if user:
        context["recent"] = plan_repo.list_for(user.username, limit=4)
    return templates.TemplateResponse(request=request, name=template, context=context)


@router.get("/dashboard")
async def dashboard(request: Request, user=Depends(require_page_user)):
    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={"user": user, "recent": plan_repo.list_for(user.username, limit=4)},
    )


@router.get("/planners/{kind}")
async def planner_page(kind: str, request: Request, user=Depends(require_page_user)):
    if kind not in KIND_LABELS:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request, name=f"planners/{kind}.html",
        context={"user": user, "kind": kind, "kind_label": KIND_LABELS[kind]},
    )


@router.get("/history")
async def history_page(
    request: Request,
    user=Depends(require_page_user),
    kind: str | None = Query(default=None),
):
    if kind is not None and kind not in KIND_LABELS:
        kind = None
    plans = plan_repo.list_for(user.username, kind=kind)
    counts = {k: plan_repo.list_for(user.username, kind=k, limit=1000) for k in KIND_LABELS}
    return templates.TemplateResponse(
        request=request, name="history.html",
        context={
            "user": user,
            "plans": plans,
            "active_kind": kind,
            "counts": {k: len(v) for k, v in counts.items()},
        },
    )
