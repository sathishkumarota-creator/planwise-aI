"""HTML authentication flows (login, register, logout)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ...config import get_settings
from ...schemas import LoginForm, RegistrationForm
from ...security import issue_token, verify_password, hash_password
from ...storage import UserAlreadyExists, UserRepository
from ..deps import current_user, user_repo
from ..templating import get_templates

router = APIRouter()
templates = get_templates()


def _set_session(response: RedirectResponse, username: str) -> None:
    settings = get_settings()
    token = issue_token(settings, username)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        max_age=settings.token_ttl_minutes * 60,
        path="/",
    )


@router.get("/login")
async def login_page(request: Request, user=Depends(current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="auth/login.html", context={"error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(default=""),
    password: str = Form(default=""),
):
    try:
        form = LoginForm(username=username, password=password)
    except Exception:
        return templates.TemplateResponse(
            request=request, name="auth/login.html",
            context={"error": "Enter your username and password."},
        )
    if not user_repo.authenticate(form.username, form.password, verify_password):
        return templates.TemplateResponse(
            request=request, name="auth/login.html",
            context={"error": "Incorrect username or password."},
            status_code=401,
        )
    response = RedirectResponse("/dashboard", status_code=303)
    _set_session(response, form.username)
    return response


@router.get("/register")
async def register_page(request: Request, user=Depends(current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="auth/register.html", context={"error": None, "values": {}})


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(default=""),
    email: str = Form(default=""),
    password: str = Form(default=""),
    confirm_password: str = Form(default=""),
):
    values = {"username": username, "email": email}
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request, name="auth/register.html",
            context={"error": "Passwords do not match.", "values": values},
            status_code=422,
        )
    try:
        form = RegistrationForm(
            username=username, email=email, password=password, display_name=username.strip().capitalize(),
        )
    except Exception as exc:
        message = "Please check the highlighted fields."
        if getattr(exc, "errors", None):
            first = exc.errors()[0]
            message = str(first.get("msg", message)).removeprefix("Value error, ")
        return templates.TemplateResponse(
            request=request, name="auth/register.html",
            context={"error": message, "values": values},
            status_code=422,
        )

    try:
        created = user_repo.create(
            username=form.username,
            email=form.email,
            password_hash=hash_password(form.password),
            display_name=form.display_name or form.username.capitalize(),
        )
    except UserAlreadyExists as exc:
        label = "Email" if exc.field == "email" else "Username"
        return templates.TemplateResponse(
            request=request, name="auth/register.html",
            context={"error": f"{label} is already registered.", "values": values},
            status_code=409,
        )

    response = RedirectResponse("/dashboard", status_code=303)
    _set_session(response, created.username)
    return response


@router.get("/logout")
@router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    return response
