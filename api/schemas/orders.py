"""Orders schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class OrderSchema(APIModel):
    id: int | None = None
    product_name: str = ""
    category: str | None = None
    price: float = 0
    quantity: int = 0
    status: str = ""
    created_at: str | None = None
    image_path: str | None = None


class OrdersResponse(APIModel):
    orders: list[OrderSchema]
    total_orders: int
    total_spent: float


class StatusUpdateResponse(APIModel):
    ok: bool
    order_id: int
    status: str
