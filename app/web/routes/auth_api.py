"""Token API and session introspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...schemas import LoginForm, TokenResponse, UserView
from ...security import issue_token, verify_password
from ..deps import require_api_user, user_repo

router = APIRouter(prefix="/api")


@router.post("/token", response_model=TokenResponse)
async def issue_access_token(form: LoginForm):
    user = user_repo.authenticate(form.username, form.password, verify_password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    settings = get_settings()
    response = JSONResponse(
        content={"access_token": issue_token(settings, user.username), "token_type": "bearer"}
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {issue_token(settings, user.username)}",
        httponly=True,
        samesite="lax",
        max_age=settings.token_ttl_minutes * 60,
        path="/",
    )
    return response


@router.get("/me", response_model=UserView)
async def who_am_i(user: UserView = Depends(require_api_user)):
    """Replaces the original /session-info; sessions are now stateless."""
    return user
