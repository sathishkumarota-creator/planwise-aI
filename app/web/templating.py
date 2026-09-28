"""Jinja environment factory shared by all route modules."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from ..schemas import format_inr

_TEMPLATES: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _TEMPLATES
    if _TEMPLATES is None:
        templates = Jinja2Templates(directory="app/web/templates")
        templates.env.filters["inr"] = format_inr
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        _TEMPLATES = templates
    return _TEMPLATES
