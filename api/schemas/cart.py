"""Cart schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class CartItemSchema(APIModel):
    id: int | None = None
    product_id: int | None = None
    product_name: str
    price: float
    quantity: int
    image_path: str | None = None
    color: str | None = None
    category: str | None = None


class CartResponse(APIModel):
    items: list[CartItemSchema]
    count: int
    total: float


class CartActionResponse(APIModel):
    success: bool = True
    message: str | None = None
    cart_total_items: int | None = None
    cart_total_price: float | None = None


class CheckoutResponse(APIModel):
    success: bool
    message: str
    order_ids: list[int] = Field(default_factory=list)
    total: float = 0
    item_count: int = 0
