"""Pure-ASGI request body size cap for upload/import routes.

Unlike a dependency, this runs before the framework buffers the body: a large
Content-Length is rejected without reading anything, and chunked requests with no
Content-Length are cut off as soon as the byte count passes the cap.
"""

import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.services.import_service import IMPORT_MAX_BYTES
from app.services.upload_service import AVATAR_MAX_BYTES, MULTIPART_SLACK

logger = logging.getLogger(__name__)


def body_cap_for(method: str, path: str) -> int | None:
    """Max allowed file bytes for the route, or None when the path is not capped."""
    prefix = settings.API_V1_PREFIX
    if method == "POST" and path == f"{prefix}/uploads/avatar":
        return AVATAR_MAX_BYTES
    if path.startswith(f"{prefix}/imports/"):
        return IMPORT_MAX_BYTES
    return None


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = body_cap_for(scope["method"], scope["path"])
        if limit is None:
            await self.app(scope, receive, send)
            return

        cap = limit + MULTIPART_SLACK
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break  # the route's own guard answers with a 400
                if declared > cap:
                    await self._reject(send, limit)
                    return
                break

        received = 0
        too_large = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > cap:
                    too_large = True
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if too_large:
                return  # whatever the app answers after the cut-off is replaced by our 413
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except Exception:
            # The framework may wrap the abort (e.g. into a 400 parse error); the cap wins.
            if not too_large or started:
                raise
        if too_large and not started:
            await self._reject(send, limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File is too large (max {limit // 1024} KB)",
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
