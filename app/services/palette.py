"""Outfit photo palette analysis.

The original mapped thumbnail pixels through a hand-written RGB threshold
ladder to get color names. This implementation converts to HSV and buckets by
hue wheel position, which behaves consistently across saturation/brightness
extremes (the RGB ladder misclassified dark reds as "black" and pale yellows
as "white").
"""

from __future__ import annotations

import colorsys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

HueBucket = tuple[str, tuple[float, float]]  # (display name, hue range in [0,1))

_HUE_BUCKETS: list[HueBucket] = [
    ("red", (0.0, 0.04)),
    ("orange", (0.04, 0.11)),
    ("gold", (0.11, 0.18)),
    ("yellow", (0.18, 0.28)),
    ("green", (0.28, 0.45)),
    ("teal", (0.45, 0.52)),
    ("blue", (0.52, 0.68)),
    ("indigo", (0.68, 0.76)),
    ("purple", (0.76, 0.87)),
    ("pink", (0.87, 0.97)),
    ("red", (0.97, 1.0)),
]

_NEUTRAL_TONE = "ivory"
_DARK_TONE = "charcoal"
_SATURATION_FLOOR = 0.18
_VALUE_FLOOR = 0.16
_VALUE_CEILING = 0.92


@dataclass
class PaletteReading:
    colors: list[str]
    style: str
    formality: str

    def as_dict(self) -> dict:
        return {"colors": self.colors, "style": self.style, "formality": self.formality}


def _bucket_for(hue: float) -> str:
    for name, (low, high) in _HUE_BUCKETS:
        if low <= hue < high:
            return name
    return "neutral"


def _describe_pixel(h: float, s: float, v: float) -> str:
    if s < _SATURATION_FLOOR or v < _VALUE_FLOOR or v > _VALUE_CEILING:
        return _DARK_TONE if v < _VALUE_FLOOR else _NEUTRAL_TONE
    return _bucket_for(h)


def _display_names(buckets: Counter[str]) -> list[str]:
    pretty = {
        "red": "Ruby Red", "orange": "Burnt Orange", "gold": "Antique Gold",
        "yellow": "Marigold", "green": "Emerald", "teal": "Teal",
        "blue": "Royal Blue", "indigo": "Indigo", "purple": "Violet",
        "pink": "Rose Pink", "ivory": "Ivory", "charcoal": "Charcoal",
        "neutral": "Neutral",
    }
    ordered = [name for name, _ in buckets.most_common(4)]
    return [pretty.get(name, name.title()) for name in ordered]


def analyze(path: str | Path) -> PaletteReading | None:
    """Return dominant colors of the outfit photo, or None if unreadable."""
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB").resize((64, 64))
    except (OSError, UnidentifiedImageError):
        return None

    pixels = rgb.getdata()
    counts: Counter[str] = Counter()
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        counts[_describe_pixel(h, s, v)] += 1

    colors = _display_names(counts) or ["Ivory"]
    # Formality heuristic: mostly neutrals/dark tones reads as formal evening
    # wear; vivid multi-hue palettes read as festive.
    vivid = sum(n for name, n in counts.items() if name not in ("ivory", "charcoal", "neutral"))
    total = sum(counts.values())
    if vivid / total < 0.25:
        style, formality = "Minimal Evening", "Formal"
    elif vivid / total > 0.6:
        style, formality = "Festive Traditional", "Semi-Formal"
    else:
        style, formality = "Indo-Western", "Semi-Formal"
    return PaletteReading(colors=colors[:3], style=style, formality=formality)
