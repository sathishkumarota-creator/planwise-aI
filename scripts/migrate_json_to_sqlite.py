"""Migrate the legacy JSON database (data/database.json) into SQLite.

Run once:  .venv/Scripts/python.exe scripts/migrate_json_to_sqlite.py

Carries over bcrypt password hashes verbatim, so existing users keep their
credentials. Legacy plan kinds ("party") are remapped to the new taxonomy
("event"). Safe to re-run: existing rows are skipped by primary key.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.storage import init_schema  # noqa: E402
from app.storage.database import connect  # noqa: E402

KIND_MAP = {"home": "home", "party": "event", "event": "event", "jewelry": "jewelry"}


def _parse_ts(raw: str) -> str:
    try:
        return datetime.fromisoformat(raw).isoformat()
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat()


def migrate(json_path: str = "data/database.json") -> None:
    legacy = Path(json_path)
    if not legacy.exists():
        print(f"No legacy database at {json_path} - nothing to migrate.")
        return

    init_schema()
    data = json.loads(legacy.read_text(encoding="utf-8"))

    conn = connect()
    imported_users = imported_plans = skipped_plans = 0
    try:
        for username, user in data.get("users", {}).items():
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (username, email, display_name, password_hash, is_disabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.get("username", username),
                    user.get("email", f"{username}@example.com"),
                    user.get("full_name", ""),
                    user["hashed_password"],
                    1 if user.get("disabled") else 0,
                    _parse_ts(user.get("created_at")),
                ),
            )
            imported_users += conn.total_changes and 1 or 0

        for username, plans in data.get("recommendations", {}).items():
            if conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone() is None:
                print(f"  ! skipping {len(plans)} plans for unknown user '{username}'")
                continue
            for plan in plans:
                kind = KIND_MAP.get(plan.get("recommendation_type", ""))
                if kind is None:
                    skipped_plans += 1
                    continue
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO plans
                        (id, username, kind, title, spec, report, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan.get("id"),
                        username,
                        kind,
                        f"{kind.capitalize()} plan (imported)",
                        json.dumps(plan.get("input_summary", {})),
                        json.dumps(plan.get("full_result", {})),
                        _parse_ts(plan.get("created_at")),
                    ),
                )
                imported_plans += cursor.rowcount
                if cursor.rowcount == 0:
                    skipped_plans += 1

        conn.commit()
    finally:
        conn.close()

    print(f"Users present: {imported_users}; plans imported: {imported_plans}; skipped: {skipped_plans}")
    print(f"SQLite database: {get_settings().db_path}")


if __name__ == "__main__":
    migrate(*sys.argv[1:])
