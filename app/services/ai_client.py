"""AI planner client.

`AiPlanner` is the seam between the planning engine and any LLM. The Gemini
implementation returns parsed JSON or None (never raises); `NullAiPlanner`
keeps the app fully functional without a key, mirroring the original's
offline mode but behind an explicit interface instead of module globals.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Protocol

from ..config import Settings

logger = logging.getLogger("planwise.ai")


class AiPlanner(Protocol):
    def complete_json(self, prompt: str, image_path: str | None = None) -> Optional[dict]: ...


def _extract_json(text: str) -> Optional[dict]:
    """Parse the first JSON object found in an LLM reply (handles code fences)."""
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class GeminiAiPlanner:
    """Thin adapter over google-generativeai with graceful failure."""

    def __init__(self, settings: Settings) -> None:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key or "")
        self._model = genai.GenerativeModel(settings.gemini_model)

    def complete_json(self, prompt: str, image_path: str | None = None) -> Optional[dict]:
        try:
            if image_path:
                from PIL import Image

                with Image.open(image_path) as image:
                    response = self._model.generate_content([prompt, image])
            else:
                response = self._model.generate_content(prompt)
            return _extract_json(response.text)
        except Exception:  # network, quota, parsing - planning must not crash
            logger.exception("Gemini completion failed; falling back to catalog")
            return None


class NullAiPlanner:
    """Offline stand-in used when no API key is configured."""

    def complete_json(self, prompt: str, image_path: str | None = None) -> Optional[dict]:
        return None


def build_ai_planner(settings: Settings) -> AiPlanner:
    if settings.gemini_api_key:
        try:
            return GeminiAiPlanner(settings)
        except Exception:
            logger.exception("Could not initialize Gemini; running without AI")
    return NullAiPlanner()


_planner: AiPlanner | None = None


def get_planner() -> AiPlanner:
    """Process-wide planner, built lazily so config changes need a restart."""
    global _planner
    if _planner is None:
        from ..config import get_settings

        _planner = build_ai_planner(get_settings())
    return _planner
