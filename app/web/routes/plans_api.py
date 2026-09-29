"""Plan lifecycle API: create, list, read, delete, export."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from ...schemas import (
    PlanRecord,
    PlanRequest,
    PlanningKind,
    UserView,
    utcnow,
)
from ...services.ai_client import get_planner
from ...services.engine import create_plan
from ...uploads import UploadRejected, save_photo
from ...storage import PlanRepository
from ..deps import require_api_user

router = APIRouter(prefix="/api/plans")
plan_repo = PlanRepository()


@router.post("")
async def generate_plan(
    payload: PlanRequest,
    user: UserView = Depends(require_api_user),
):
    """One endpoint for all three planners; kind is taken from spec.kind."""
    kind = payload.spec.kind
    report = create_plan(kind, payload.spec, get_planner())
    plan_id = uuid.uuid4().hex[:12]
    record = PlanRecord(
        id=plan_id,
        username=user.username,
        kind=kind,  # type: ignore[arg-type]
        title=payload.title.strip() or _default_title(kind),
        spec=payload.spec.model_dump(mode="json"),
        report=report.to_dict(),
        created_at=utcnow(),
    )
    plan_repo.add(record)
    return {"id": plan_id, "title": record.title, "report": report.to_dict()}


@router.get("")
async def list_plans(
    kind: str | None = None,
    limit: int = 50,
    user: UserView = Depends(require_api_user),
):
    if kind is not None and kind not in PlanningKind.__args__:
        raise HTTPException(422, "Unknown plan kind filter.")
    summaries = plan_repo.list_for(user.username, kind=kind, limit=min(limit, 200))
    return {
        "plans": [
            {
                "id": s.id,
                "kind": s.kind,
                "title": s.title,
                "budget": s.budget,
                "planned_total": s.planned_total,
                "remaining": s.remaining,
                "created_at": s.created_at.isoformat(),
            }
            for s in summaries
        ]
    }


@router.get("/export.csv")
async def export_csv(user: UserView = Depends(require_api_user)):
    summaries = plan_repo.list_for(user.username, limit=1000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "title", "kind", "budget_inr", "planned_total_inr", "remaining_inr", "created_at"])
    for s in summaries:
        writer.writerow(
            [s.id, s.title, s.kind, s.budget, s.planned_total, s.remaining, s.created_at.isoformat()]
        )
    buffer.seek(0)
    filename = f"planwise-{user.username}-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/photos/{photo_id}")
async def serve_outfit_photo(
    photo_id: str,
    user: UserView = Depends(require_api_user),
):
    """Authenticated proxy for uploaded photos (they are not publicly served)."""
    from fastapi.responses import FileResponse

    from ...uploads import resolve_upload_path

    path = resolve_upload_path(photo_id)
    if not path:
        raise HTTPException(404, "Photo not found.")
    return FileResponse(path)


@router.get("/{plan_id}")
async def plan_details(plan_id: str, user: UserView = Depends(require_api_user)):
    record = plan_repo.get(user.username, plan_id)
    if not record:
        raise HTTPException(404, "Plan not found.")
    return {
        "id": record.id,
        "kind": record.kind,
        "title": record.title,
        "created_at": record.created_at.isoformat(),
        "spec": record.spec,
        "report": record.report,
    }


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, user: UserView = Depends(require_api_user)):
    if not plan_repo.delete(user.username, plan_id):
        raise HTTPException(404, "Plan not found.")
    return {"deleted": plan_id}


@router.post("/outfit-photo")
async def upload_outfit_photo(
    photo: UploadFile = File(...),
    user: UserView = Depends(require_api_user),
):
    """Store an outfit photo privately; returns the id to reference in a plan."""
    try:
        photo_id = save_photo(photo)
    except UploadRejected as exc:
        raise HTTPException(422, str(exc))
    return {"photo_id": photo_id}




def _default_title(kind: str) -> str:
    stamps = {"home": "Home interior plan", "event": "Event plan", "jewelry": "Jewelry plan"}
    return f"{stamps.get(kind, 'Plan')} - {datetime.now(timezone.utc):%d %b %Y %H:%M}"
