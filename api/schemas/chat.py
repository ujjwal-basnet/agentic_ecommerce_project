"""Chat schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class HealthResponse(APIModel):
    status: str


class RootResponse(APIModel):
    app: str
    version: str
    status: str


class UploadPhotoResponse(APIModel):
    path: str
    session_id: str


class ClearChatResponse(APIModel):
    ok: bool


class ChatEvent(APIModel):
    type: Literal["text", "tool_result", "cart_sync", "image", "error"]
    content: str | None = None
    component: str | None = None
    data: dict[str, Any] | None = None
    products: list[dict[str, Any]] | None = None
    cart_count: int | None = None
    image_path: str | None = None


class TrackViewResponse(APIModel):
    ok: bool
