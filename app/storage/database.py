"""SQLite persistence layer (replaces the JSON file store).

One connection per call is intentional: it keeps the module import-safe under
uvicorn's reloader and avoids cross-thread connection sharing issues. WAL mode
allows readers to run alongside the occasional write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    email        TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    is_disabled  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id         TEXT PRIMARY KEY,
    username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('home', 'event', 'jewelry')),
    title      TEXT NOT NULL DEFAULT '',
    spec       TEXT NOT NULL,   -- JSON of the planning inputs
    report     TEXT NOT NULL,   -- JSON of the generated report
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(username, created_at DESC);
"""

_CONNECTION_KWARGS = {"detect_types": 0, "timeout": 10}


def connect() -> sqlite3.Connection:
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, **_CONNECTION_KWARGS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
