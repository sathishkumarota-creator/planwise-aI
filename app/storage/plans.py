"""Saved-plan persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ..schemas import PlanRecord, PlanSummary, PlanningKind
from .database import connect

_KINDS: tuple[str, ...] = ("home", "event", "jewelry")


def _row_to_record(row: sqlite3.Row) -> PlanRecord:
    return PlanRecord(
        id=row["id"],
        username=row["username"],
        kind=row["kind"],
        title=row["title"],
        spec=json.loads(row["spec"]),
        report=json.loads(row["report"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class PlanRepository:
    def add(self, record: PlanRecord) -> PlanRecord:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO plans (id, username, kind, title, spec, report, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.username,
                    record.kind,
                    record.title,
                    json.dumps(record.spec),
                    json.dumps(record.report),
                    record.created_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return record

    def list_for(self, username: str, kind: Optional[str] = None, limit: int = 200) -> list[PlanSummary]:
        query = (
            "SELECT id, username, kind, title, report, created_at FROM plans "
            "WHERE username = ?"
        )
        params: list = [username]
        if kind in _KINDS:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        conn = connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        summaries = []
        for row in rows:
            report = json.loads(row["report"])
            summaries.append(
                PlanSummary(
                    id=row["id"],
                    kind=row["kind"],
                    title=row["title"],
                    budget=float(report.get("budget", 0.0)),
                    planned_total=float(report.get("planned_total", 0.0)),
                    remaining=float(report.get("remaining", 0.0)),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return summaries

    def get(self, username: str, plan_id: str) -> Optional[PlanRecord]:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM plans WHERE id = ? AND username = ?",
                (plan_id, username),
            ).fetchone()
        finally:
            conn.close()
        return _row_to_record(row) if row else None

    def delete(self, username: str, plan_id: str) -> bool:
        conn = connect()
        try:
            cursor = conn.execute(
                "DELETE FROM plans WHERE id = ? AND username = ?",
                (plan_id, username),
            )
            conn.commit()
        finally:
            conn.close()
        return cursor.rowcount > 0

    def count(self, username: Optional[str] = None) -> int:
        conn = connect()
        try:
            if username is None:
                row = conn.execute("SELECT COUNT(*) AS n FROM plans").fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM plans WHERE username = ?", (username,)
                ).fetchone()
        finally:
            conn.close()
        return int(row["n"])
