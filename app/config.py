"""Central configuration.

Settings are read once from the environment; nothing else in the codebase is
allowed to call os.getenv directly, so configuration stays auditable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

_DEFAULT_SECRET = "planwise-insecure-dev-secret-change-me"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the whole application."""

    app_name: str = "PlanWise"
    secret_key: str = _DEFAULT_SECRET
    token_ttl_minutes: int = 120
    host: str = "0.0.0.0"
    port: int = 8000

    # SQLite lives under data/ which also holds uploaded outfit photos.
    data_dir: str = "data"
    db_path: str = os.path.join("data", "planwise.sqlite3")

    # Uploads are stored outside any web-served directory on purpose.
    upload_dir: str = os.path.join("data", "uploads")
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_allowed_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Reserve share of the budget the catalog strategies keep unspent by default.
    reserve_ratio: float = 0.05

    cors_origins: tuple[str, ...] = ()
    seed_demo_user: bool = True
    demo_username: str = "sai"
    demo_password: str = "password123"

    @classmethod
    def load(cls) -> "Settings":
        origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]
        api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip() or None
        # Vercel's deployed filesystem is read-only except for /tmp.
        # Keep the default local layout for normal servers, but move ephemeral
        # runtime state to /tmp when running as a Vercel function.
        on_vercel = os.getenv("VERCEL", "").strip().lower() == "1"
        runtime_dir = os.path.join("/tmp", "planwise") if on_vercel else "data"
        return cls(
            secret_key=os.getenv("SECRET_KEY", _DEFAULT_SECRET),
            token_ttl_minutes=_int_env("TOKEN_TTL_MINUTES", 120),
            host=os.getenv("HOST", "0.0.0.0"),
            port=_int_env("PORT", 8000),
            data_dir=os.getenv("DATA_DIR", runtime_dir),
            db_path=os.getenv("DB_PATH", os.path.join(runtime_dir, "planwise.sqlite3")),
            upload_dir=os.getenv("UPLOAD_DIR", os.path.join(runtime_dir, "uploads")),
            upload_max_bytes=_int_env("UPLOAD_MAX_BYTES", 5 * 1024 * 1024),
            gemini_api_key=api_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            reserve_ratio=float(os.getenv("RESERVE_RATIO", "0.05")),
            cors_origins=tuple(origins),
            seed_demo_user=os.getenv("SEED_DEMO_USER", "1") not in ("0", "false", "no"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
