"""User account persistence."""

from __future__ import annotations

import sqlite3
from typing import Optional

from ..schemas import UserView, utcnow
from .database import connect


class UserAlreadyExists(Exception):
    def __init__(self, field: str) -> None:
        self.field = field  # "username" or "email"
        super().__init__(f"{field} already registered")


class UserRepository:
    def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        display_name: str = "",
    ) -> UserView:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO users (username, email, display_name, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, display_name, password_hash, utcnow().isoformat()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "email" in message:
                raise UserAlreadyExists("email") from exc
            raise UserAlreadyExists("username") from exc
        finally:
            conn.close()
        return UserView(username=username, email=email, display_name=display_name)

    def find(self, username: str) -> Optional[dict]:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def find_by_email(self, email: str) -> Optional[dict]:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def authenticate(self, username: str, password: str, verify) -> Optional[UserView]:
        """Verify credentials with the injected hasher and return the user view."""
        record = self.find(username)
        if not record or record["is_disabled"]:
            return None
        if not verify(password, record["password_hash"]):
            return None
        return UserView(
            username=record["username"],
            email=record["email"],
            display_name=record["display_name"],
        )

    def seed_demo_user(self, username: str, password_hash: str, email: str) -> None:
        if self.find(username) is None:
            self.create(username, email, password_hash, display_name="Demo User")
