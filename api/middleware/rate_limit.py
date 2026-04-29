"""In-memory token-bucket rate limiter (pure ASGI).

Single-process; good for Render / one-replica deploys. For horizontal scaling
swap the `_BUCKETS` dict for a Redis-backed implementation. Keys are derived
from the Authorization Bearer JWT (sub claim) or the client IP.

Path tiers:
  /chat/stream                       -> RATE_LIMIT_CHAT
  /owner/campaign/visual             -> RATE_LIMIT_HEAVY
  /specialist/tryon                  -> RATE_LIMIT_HEAVY
  everything else                    -> RATE_LIMIT_DEFAULT
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Tuple

import jwt

from api import config

logger = logging.getLogger(__name__)

# {key: [tokens_remaining, last_refill_ts]}
_BUCKETS: dict[str, list[float]] = {}
_BUCKETS_LOCK = asyncio.Lock()

_HEAVY_PATHS = ("/owner/campaign/visual", "/specialist/tryon")
_CHAT_PATHS = ("/chat/stream", "/api/chat")
_PUBLIC_PATHS = frozenset({"/", "/health", "/openapi.json", "/docs", "/redoc"})


def _bucket_for(path: str) -> Tuple[int, int]:
    """Return (capacity, window_seconds) for the path."""
    if any(path.startswith(p) for p in _HEAVY_PATHS):
        return config.RATE_LIMIT_HEAVY
    if any(path.startswith(p) for p in _CHAT_PATHS):
        return config.RATE_LIMIT_CHAT
    return config.RATE_LIMIT_DEFAULT


def _client_key(scope) -> str:
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            payload = jwt.decode(
                token,
                config.JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            sub = payload.get("sub")
            if sub:
                return f"u:{sub}"
        except jwt.InvalidTokenError:
            pass
    client = scope.get("client") or ("anon", 0)
    return f"ip:{client[0]}"


async def _consume(key: str, capacity: int, window: int) -> tuple[bool, float]:
    """Token-bucket consume. Returns (allowed, retry_after_seconds)."""
    if capacity <= 0 or window <= 0:
        return True, 0.0
    rate = capacity / window  # tokens per second
    now = time.monotonic()
    async with _BUCKETS_LOCK:
        bucket = _BUCKETS.get(key)
        if bucket is None:
            _BUCKETS[key] = [capacity - 1, now]
            return True, 0.0
        tokens, last = bucket
        tokens = min(capacity, tokens + (now - last) * rate)
        if tokens >= 1:
            bucket[0] = tokens - 1
            bucket[1] = now
            return True, 0.0
        bucket[0] = tokens
        bucket[1] = now
        retry = (1 - tokens) / rate
        return False, retry


async def _send_429(send, retry_after: float):
    body = json.dumps(
        {
            "error": "rate_limited",
            "retry_after": round(retry_after, 2),
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
                [b"retry-after", str(max(1, int(retry_after))).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    """Pure ASGI middleware. No-op when RATE_LIMIT_ENABLED=false."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not config.RATE_LIMIT_ENABLED:
            return await self.app(scope, receive, send)

        # Let browser CORS preflight reach CORSMiddleware without spending tokens.
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        path = scope["path"].rstrip("/") or "/"
        if (
            path in _PUBLIC_PATHS
            or path.startswith("/data/")
            or path.startswith("/mcp")
        ):
            return await self.app(scope, receive, send)

        capacity, window = _bucket_for(path)
        key = f"{_client_key(scope)}:{path[:64]}"
        allowed, retry = await _consume(key, capacity, window)
        if not allowed:
            logger.warning("rate_limited key=%s path=%s retry=%.2fs", key, path, retry)
            return await _send_429(send, retry)
        return await self.app(scope, receive, send)
