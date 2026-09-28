"""Password hashing and token issuing.

Replaces python-jose (unmaintained) with PyJWT and keeps the bcrypt helpers
thin. Tokens are self-contained statelessly - no server-side session registry
to clean up or lose on restart.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import bcrypt
import jwt

from .config import Settings


class PasswordHasher:
    """bcrypt wrapper; passwords are truncated to bcrypt's 72-byte limit."""

    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode()[:72], hashed.encode())
        except (ValueError, TypeError):
            return False


def hash_password(password: str) -> str:
    return PasswordHasher().hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return PasswordHasher().verify(password, hashed)


def issue_token(settings: Settings, subject: str) -> str:
    now = _utc_timestamp()
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + settings.token_ttl_minutes * 60,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def read_token(settings: Settings, token: str) -> str | None:
    """Return the username encoded in `token`, or None when invalid/expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


def _utc_timestamp() -> int:
    import time

    return int(time.time())
