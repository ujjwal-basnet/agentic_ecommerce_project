"""Products schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class ProductSchema(APIModel):
    id: int | None = None
    name: str = ""
    category: str | None = None
    color: str | None = None
    price: float = 0
    description: str | None = None
    quantity: int = 0
    image_path: str | None = None
    tags: Any = None
    is_wearable: bool | int = False
    indexed: bool | int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProductCreateResponse(APIModel):
    success: bool
    product_id: int


class ProductDeleteResponse(APIModel):
    ok: bool


class ProductUpdateResponse(APIModel):
    success: bool
