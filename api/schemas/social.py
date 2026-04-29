"""Social schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class SocialPostResponse(APIModel):
    status: str | None = None
    success: bool | None = None
    message: str | None = None
    id: str | None = None


class TryOnResponse(APIModel):
    success: bool | None = None
    image_path: str | None = None
    message: str | None = None
    error: str | None = None


class CaptionRestyleResponse(APIModel):
    caption: str
    tone: str
    language: str = "en"


class VisualGenerateResponse(APIModel):
    success: bool
    image_path: str | None = None
    image_url: str | None = None
    error: str | None = None


class LaunchCampaignResponse(APIModel):
    ok: bool
    deployed: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)
