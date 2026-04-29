"""Per-request context propagated through the async stack via contextvars.

ASGI middleware extracts/generates a request id and stores it so structured log
records can attach it without plumbing it through every function signature.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    return _request_id_var.get()


def set_request_id(value: str) -> None:
    _request_id_var.set(value)


class RequestIdMiddleware:
    """Pure ASGI middleware — sets request_id contextvar + echoes header."""

    HEADER = b"x-request-id"

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        incoming = headers.get(self.HEADER, b"").decode().strip()
        rid = incoming or uuid.uuid4().hex[:16]
        token = _request_id_var.set(rid)

        async def _send_with_header(message):
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                msg_headers.append((self.HEADER, rid.encode()))
                message = {**message, "headers": msg_headers}
            await send(message)

        try:
            await self.app(scope, receive, _send_with_header)
        finally:
            _request_id_var.reset(token)
