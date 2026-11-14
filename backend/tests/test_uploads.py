"""Tests for avatar uploads (magic-byte validation, size limits, replacement)."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user
from app.main import app
from app.models.user import User

URL = "/api/v1/uploads/avatar"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16


@pytest.fixture
def users(client: TestClient, db_session: Session, tmp_path: Path) -> Iterator[dict[int, User]]:
    old = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path / "up")
    out: dict[int, User] = {}
    for uid in (1, 2):
        u = User(id=uid, email=f"u{uid}@example.com")
        db_session.add(u)
        out[uid] = u
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: out[1]
    yield out
    app.dependency_overrides.pop(get_current_user, None)
    settings.UPLOAD_DIR = old


def _post(
    client: TestClient, data: bytes, name: str = "a.png", ctype: str = "image/png"
) -> httpx.Response:
    return client.post(URL, files={"file": (name, data, ctype)})


def test_requires_auth(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert _post(client, PNG).status_code == 401
    assert client.delete(URL).status_code == 401


@pytest.mark.parametrize(
    ("data", "ctype"), [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")]
)
def test_upload_and_fetch(
    client: TestClient, users: dict[int, User], data: bytes, ctype: str
) -> None:
    r = _post(client, data, "x.bin", "application/octet-stream")  # client type is ignored
    assert r.status_code == 200
    assert r.json() == {"updated": True}
    g = client.get(URL)
    assert g.status_code == 200
    assert g.content == data
    assert g.headers["content-type"] == ctype
    assert g.headers["x-content-type-options"] == "nosniff"


def test_get_404_when_none_and_delete(client: TestClient, users: dict[int, User]) -> None:
    assert client.get(URL).status_code == 404
    _post(client, PNG)
    assert client.delete(URL).status_code == 204
    assert client.get(URL).status_code == 404
    assert client.delete(URL).status_code == 204


def test_wrong_magic_bytes_with_image_content_type(
    client: TestClient, users: dict[int, User]
) -> None:
    r = _post(client, b"<script>alert(1)</script>", "evil.png", "image/png")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "INVALID_FILE"
    assert client.get(URL).status_code == 404
    assert _post(client, b"GIF89a....", "a.png", "image/png").status_code == 415
    assert _post(client, b"", "a.png", "image/png").status_code == 400


def test_oversize_rejected(client: TestClient, users: dict[int, User]) -> None:
    r = _post(client, PNG + b"\x00" * (2 * 1024 * 1024))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"
    exact = PNG + b"\x00" * (2 * 1024 * 1024 - len(PNG))
    assert _post(client, exact).status_code == 200


def test_path_traversal_filename_ignored(
    client: TestClient, users: dict[int, User], tmp_path: Path
) -> None:
    r = _post(client, PNG, "../../../evil.png")
    assert r.status_code == 200
    stored = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert stored == ["up/avatars/1.png"]


def test_replace_removes_old_extension(
    client: TestClient, users: dict[int, User], tmp_path: Path
) -> None:
    _post(client, PNG)
    _post(client, JPEG, "b.jpg", "image/jpeg")
    files = sorted(p.name for p in (tmp_path / "up" / "avatars").iterdir())
    assert files == ["1.jpg"]
    assert client.get(URL).headers["content-type"] == "image/jpeg"


def test_avatars_are_per_user(client: TestClient, users: dict[int, User]) -> None:
    _post(client, PNG)
    app.dependency_overrides[get_current_user] = lambda: users[2]
    assert client.get(URL).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: users[1]
    assert client.get(URL).status_code == 200


def test_missing_file_field(client: TestClient, users: dict[int, User]) -> None:
    assert client.post(URL).status_code == 422
