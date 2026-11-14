"""Avatar storage on disk plus shared, size-bounded upload reading.

Files are keyed by user id only; client-supplied names and content types are
never used for paths or for deciding what a file is.
"""

import contextlib
import logging
import os
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.exceptions import AppException, NotFoundError

logger = logging.getLogger(__name__)

AVATAR_MAX_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
# Multipart framing overhead allowed on top of the file limit when checking Content-Length.
MULTIPART_SLACK = 16 * 1024

# extension -> content type; the extension is derived from magic bytes only.
AVATAR_TYPES: dict[str, str] = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


class FileTooLargeError(AppException):
    def __init__(self, limit_bytes: int) -> None:
        super().__init__(f"File is too large (max {limit_bytes // 1024} KB)", "FILE_TOO_LARGE", 413)


class InvalidFileError(AppException):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message, "INVALID_FILE", status_code)


def content_length_guard(max_bytes: int) -> Callable[[Request], None]:
    """Dependency factory: reject oversize requests from the Content-Length header early."""

    def _guard(request: Request) -> None:
        raw = request.headers.get("content-length")
        if raw is not None:
            try:
                length = int(raw)
            except ValueError:
                raise InvalidFileError("Invalid Content-Length header") from None
            if length > max_bytes + MULTIPART_SLACK:
                raise FileTooLargeError(max_bytes)

    return _guard


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, aborting as soon as max_bytes is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def sniff_image(data: bytes) -> str | None:
    """Return 'png' | 'jpg' | 'webp' from magic bytes, else None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _avatar_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / "avatars"


def _avatar_path(user_id: int, ext: str) -> Path:
    return _avatar_dir() / f"{int(user_id)}.{ext}"


def _store(user_id: int, ext: str, data: bytes) -> None:
    directory = _avatar_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_bytes(data)
        os.replace(tmp, _avatar_path(user_id, ext))
    finally:
        tmp.unlink(missing_ok=True)
    for other in AVATAR_TYPES:
        if other != ext:
            _avatar_path(user_id, other).unlink(missing_ok=True)


async def save_avatar(user_id: int, file: UploadFile) -> None:
    data = await read_limited(file, AVATAR_MAX_BYTES)
    if not data:
        raise InvalidFileError("Uploaded file is empty")
    ext = sniff_image(data)
    if ext is None:
        raise InvalidFileError("Unsupported image type; use PNG, JPEG or WebP", 415)
    await run_in_threadpool(_store, user_id, ext, data)


def load_avatar(user_id: int) -> tuple[bytes, str]:
    for ext, content_type in AVATAR_TYPES.items():
        path = _avatar_path(user_id, ext)
        with contextlib.suppress(FileNotFoundError):
            return path.read_bytes(), content_type
    raise NotFoundError("Avatar")


def delete_avatar(user_id: int) -> None:
    for ext in AVATAR_TYPES:
        _avatar_path(user_id, ext).unlink(missing_ok=True)
