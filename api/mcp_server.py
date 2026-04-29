"""Remote MCP adapter for Claude/Cursor clients.

This exposes the existing ecommerce engine as MCP tools. It is not a second
engine; tools call engine.run(..., channel="text") so behavior stays shared
with Instagram/Facebook text channels.
"""

from __future__ import annotations

import secrets
import uuid

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api import config, engine

mcp = FastMCP("SmartShop Assistant")


def _normalize_session_id(session_id: str | None) -> str:
    cleaned = (session_id or "").strip()
    if not cleaned:
        cleaned = uuid.uuid4().hex[:12]
    if cleaned.startswith("mcp_"):
        return cleaned
    return f"mcp_{cleaned}"


class MCPBearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = config.MCP_BEARER_TOKEN.strip()
        if not expected:
            return JSONResponse(
                {"error": "MCP_BEARER_TOKEN is not configured"},
                status_code=503,
            )

        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(token, expected):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)


@mcp.tool
async def chat(message: str, session_id: str | None = None) -> dict:
    """Chat with the SmartShop ecommerce assistant."""
    sid = _normalize_session_id(session_id)
    result = await engine.run(message, channel="text", session_id=sid)
    return {
        "text": result.get("text", ""),
        "session_id": result.get("session_id", sid),
        "cart_count": result.get("cart_count", 0),
    }


mcp_app = mcp.http_app(
    path="/",
    middleware=[Middleware(MCPBearerAuthMiddleware)],
)
