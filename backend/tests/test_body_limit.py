"""Pure-ASGI body size cap: rejects before the app buffers the body."""

import asyncio
from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from app.middleware import BodySizeLimitMiddleware, body_cap_for
from app.models.user import User
from app.services.import_service import IMPORT_MAX_BYTES
from app.services.upload_service import AVATAR_MAX_BYTES, MULTIPART_SLACK
from tests.test_uploads import PNG, users  # noqa: F401

AVATAR = "/api/v1/uploads/avatar"
IMPORT = "/api/v1/imports/asins"
CAP = AVATAR_MAX_BYTES + MULTIPART_SLACK


def _chunks(total: int, size: int = 64 * 1024) -> Iterator[bytes]:
    sent = 0
    while sent < total:
        n = min(size, total - sent)
        sent += n
        yield b"x" * n


def test_caps_by_path() -> None:
    assert body_cap_for("POST", AVATAR) == AVATAR_MAX_BYTES
    assert body_cap_for("GET", AVATAR) is None
    assert body_cap_for("POST", IMPORT) == IMPORT_MAX_BYTES
    assert body_cap_for("POST", "/api/v1/imports/cost-sheet") == IMPORT_MAX_BYTES
    assert body_cap_for("POST", "/api/v1/auth/login") is None


def test_content_length_rejected_without_reading_body() -> None:
    called = False

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        nonlocal called
        called = True

    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        raise AssertionError("body must not be read")

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": AVATAR,
        "headers": [(b"content-length", str(CAP + 1).encode())],
    }
    asyncio.run(BodySizeLimitMiddleware(inner)(scope, receive, send))
    assert not called
    assert sent[0]["status"] == 413
    assert b"FILE_TOO_LARGE" in sent[1]["body"]


def test_oversized_content_length_http(client: TestClient) -> None:
    r = client.post(
        AVATAR,
        content=b"x" * 10,
        headers={"content-length": str(CAP + 1), "content-type": "multipart/form-data; boundary=b"},
    )
    # Declared length is over the cap -> 413 even before auth runs.
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_oversized_chunked_without_content_length(
    client: TestClient,
    users: dict[int, User],  # noqa: F811
) -> None:
    req = client.build_request(
        "POST",
        AVATAR,
        content=_chunks(CAP + 200_000),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    assert "content-length" not in req.headers
    r = client.send(req)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_oversized_chunked_import(client: TestClient) -> None:
    req = client.build_request(
        "POST",
        IMPORT,
        content=_chunks(IMPORT_MAX_BYTES + MULTIPART_SLACK + 100_000),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    r = client.send(req)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_normal_uploads_still_work(client: TestClient, users: dict[int, User]) -> None:  # noqa: F811
    r = client.post(AVATAR, files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 200
    exact = PNG + b"\x00" * (AVATAR_MAX_BYTES - len(PNG))
    assert client.post(AVATAR, files={"file": ("a.png", exact, "image/png")}).status_code == 200
    csv = b"asin\nB012345678\n"
    r = client.post(
        IMPORT, params={"new_list_name": "L"}, files={"file": ("a.csv", csv, "text/csv")}
    )
    assert r.status_code == 200


def test_other_routes_not_capped(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/login", content=b"x" * (CAP + 10), headers={"content-type": "text/plain"}
    )
    assert r.status_code != 413
