"""Request-scoped dependencies for authentication.

Two distinct behaviors, cleanly separated:
- pages() redirects anonymous browsers to /login instead of raising.
- api_user() returns proper 401 JSON for API callers.
The original raised 307-with-Location from a dependency, which only worked by
accident for browsers and confused API clients.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, Request
from fastapi.responses import RedirectResponse

from ..config import get_settings
from ..schemas import UserView
from ..security import read_token
from ..storage import UserRepository

user_repo = UserRepository()


def _token_from(request: Request, access_token: Optional[str]) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    if access_token:
        return access_token[7:] if access_token.startswith("Bearer ") else access_token
    return None


def current_user(request: Request, access_token: Optional[str] = Cookie(default=None)) -> Optional[UserView]:
    token = _token_from(request, access_token)
    if not token:
        return None
    username = read_token(get_settings(), token)
    if not username:
        return None
    record = user_repo.find(username)
    if not record or record["is_disabled"]:
        return None
    return UserView(
        username=record["username"],
        email=record["email"],
        display_name=record["display_name"] or record["username"].capitalize(),
    )


def require_page_user(user: Optional[UserView] = Depends(current_user)) -> UserView:
    if user is None:
        response = RedirectResponse("/login", status_code=303)
        response.headers["Location"] = "/login"
        raise _PageRedirect(response)
    return user


class _PageRedirect(Exception):
    def __init__(self, response: RedirectResponse) -> None:
        self.response = response


def require_api_user(user: Optional[UserView] = Depends(current_user)) -> UserView:
    from fastapi import HTTPException, status

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    return user
