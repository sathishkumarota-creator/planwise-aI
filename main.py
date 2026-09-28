"""PlanWise entrypoint.

Run:  .venv/Scripts/python.exe main.py
or:   .venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import uvicorn

from app.config import get_settings
from app.web.app import create_app

settings = get_settings()
app = create_app()

if __name__ == "__main__":
    print(f"Starting PlanWise on http://localhost:{settings.port}")
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
