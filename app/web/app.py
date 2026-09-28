"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..storage import PlanRepository, UserRepository, init_schema
from ..security import hash_password
from .deps import _PageRedirect, current_user
from .routes import auth_api, auth_pages, pages, plans_api
from .templating import get_templates

logger = logging.getLogger("planwise.web")


def create_app() -> FastAPI:
    settings = get_settings()
    init_schema()
    _seed_demo_user()

    app = FastAPI(title="PlanWise", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # CORS only for explicitly listed origins; credentialed requests to "*"
    # were a hole in the original design.
    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(pages.router)
    app.include_router(auth_pages.router)
    app.include_router(auth_api.router)
    app.include_router(plans_api.router)

    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

    @app.exception_handler(_PageRedirect)
    async def _handle_page_redirect(_: Request, exc: _PageRedirect):
        return exc.response

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        """Readable field errors instead of FastAPI's wall of JSON."""
        fields = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body",))
            message = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
            fields.append(f"{loc}: {message}" if loc else message)
        if _wants_html(request):
            templates = get_templates()
            return templates.TemplateResponse(
                request=request, name="error.html",
                context={"message": "Some details need fixing.", "fields": fields},
                status_code=422,
            )
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": fields})

    @app.exception_handler(Exception)
    async def _handle_crash(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        if _wants_html(request):
            templates = get_templates()
            return templates.TemplateResponse(
                request=request, name="error.html",
                context={"message": "Something went wrong on our side. Please try again.", "fields": []},
                status_code=500,
            )
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    return app


def _seed_demo_user() -> None:
    settings = get_settings()
    if not settings.seed_demo_user:
        return
    UserRepository().seed_demo_user(
        settings.demo_username,
        hash_password(settings.demo_password),
        email=f"{settings.demo_username}@planwise.local",
    )


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")
