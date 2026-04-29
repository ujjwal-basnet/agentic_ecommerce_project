"""JWT auth gate — pure ASGI middleware (no BaseHTTPMiddleware).

Using raw ASGI avoids the response-buffering issue that BaseHTTPMiddleware
causes with SSE / streaming endpoints.

Public paths (no JWT needed):
  GET  /           — root health check
  GET  /health     — health endpoint
  POST /api/gate/login — where users get their JWT
  /mcp/*           — has its own bearer token auth
"""

from __future__ import annotations

import json
import logging

import jwt

from api import config

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset(
    {
        "/",
        "/health",
        "/api/gate/login",
        "/api/gate/check",
        "/openapi.json",
        "/docs",
        "/redoc",
    }
)
_PUBLIC_PREFIXES = ("/mcp", "/data/")


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def verify_jwt(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def _send_json(send, status: int, body: dict):
    """Send a JSON response through raw ASGI."""
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(payload)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class AuthGateMiddleware:
    """Pure ASGI middleware — no response buffering, safe for SSE streams.

    When APP_USERNAME is not configured the gate is **disabled** —
    all requests pass through (local dev mode).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Let browser CORS preflight reach CORSMiddleware.
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        # Gate disabled — no credentials configured (local dev).
        if not config.APP_USERNAME:
            return await self.app(scope, receive, send)

        path = scope["path"].rstrip("/") or "/"
        if _is_public(path):
            return await self.app(scope, receive, send)

        # Extract JWT from Authorization header.
        headers = dict(scope.get("headers", []))
        auth = (headers.get(b"authorization", b"")).decode()
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return await _send_json(
                send, 401, {"error": "Authorization header required"}
            )

        payload = verify_jwt(token)
        if payload is None:
            return await _send_json(send, 401, {"error": "Invalid or expired token"})

        # Attach user to scope state (accessible via request.state.gate_user).
        scope.setdefault("state", {})["gate_user"] = payload.get("sub", "")
        return await self.app(scope, receive, send)
