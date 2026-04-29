"""Users schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class UserSchema(APIModel):
    id: int
    name: str
    email: str


class LoginResponse(APIModel):
    ok: bool
    user: UserSchema


class MeResponse(APIModel):
    user: UserSchema | None = None
