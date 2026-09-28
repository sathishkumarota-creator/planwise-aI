"""Outfit photo uploads.

Security notes, relative to the original design:
- Files are stored under data/uploads, which no route serves statically; pages
  that need to display a photo must proxy it through an authenticated route.
- Filenames are server-generated UUIDs, never client-supplied.
- Content type is checked, PIL verifies the image actually decodes, and an
  upper size limit is enforced while streaming the file to disk.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from .config import get_settings

_SAFE_ID = re.compile(r"^[0-9a-f]{32}$")

_LEGACY_EXTENSION_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class UploadRejected(Exception):
    """Raised with a user-presentable message when a photo is not acceptable."""


def save_photo(upload: UploadFile) -> str:
    """Persist an outfit photo and return its public id (32 hex chars)."""
    settings = get_settings()
    if upload.content_type not in settings.upload_allowed_types:
        raise UploadRejected("Only JPEG, PNG, or WebP images are supported.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    photo_id = uuid.uuid4().hex
    target = upload_dir / photo_id

    written = 0
    try:
        with target.open("wb") as sink:
            while chunk := upload.file.read(64 * 1024):
                written += len(chunk)
                if written > settings.upload_max_bytes:
                    raise UploadRejected("Image is larger than the 5 MB limit.")
                sink.write(chunk)
        with Image.open(target) as image:  # verify before accepting
            image.verify()
        with Image.open(target) as image:  # reopen: verify() leaves the object unusable
            image.load()
    except UploadRejected:
        target.unlink(missing_ok=True)
        raise
    except (OSError, UnidentifiedImageError):
        target.unlink(missing_ok=True)
        raise UploadRejected("That file could not be read as an image.") from None
    return photo_id


def resolve_upload_path(photo_id: str) -> Path | None:
    """Map a photo id to its on-disk path; None for anything unexpected."""
    if not _SAFE_ID.match(photo_id or ""):
        return None
    settings = get_settings()
    for extension in _LEGACY_EXTENSION_BY_TYPE.values():
        candidate = Path(settings.upload_dir) / f"{photo_id}{extension}"
        if candidate.exists():
            return candidate
    plain = Path(settings.upload_dir) / photo_id
    return plain if plain.exists() else None
