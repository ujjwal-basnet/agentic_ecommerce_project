"""Owner schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from api.schemas.core import APIModel


class AnalyticsResponse(APIModel):
    stats: dict[str, Any]
    revenue: list[dict[str, Any]]
    top: list[dict[str, Any]]
    by_cat: list[dict[str, Any]]
    stock: list[dict[str, Any]]
    orders: list[dict[str, Any]]


class OverviewStats(APIModel):
    total_revenue: float
    total_orders: int
    total_customers: int
    total_products: int
    today_revenue: float
    yesterday_revenue: float
    day_delta_pct: float


class OverviewResponse(APIModel):
    stats: OverviewStats


class ForecastPoint(APIModel):
    date: str
    value: float
    is_forecast: bool = False


class ForecastResponse(APIModel):
    range: str
    points: list[ForecastPoint]
    historical_end_index: int


class TrendingProduct(APIModel):
    product_id: int
    name: str
    price: float
    image_path: str | None = None
    score: float
    demand_pct: int
    demand_level: Literal["Peak", "High", "Med"]


class TrendingResponse(APIModel):
    products: list[TrendingProduct]


class LogisticsRow(APIModel):
    order_id: int
    user_name: str
    user_email: str | None = None
    user_initials: str
    product_name: str
    quantity: int
    revenue: float
    status: str
    created_at: str | None = None


class LogisticsResponse(APIModel):
    rows: list[LogisticsRow]


class OwnerAnalyticsResponse(APIModel):
    stats: OverviewStats
    forecast: ForecastResponse
    products: list[TrendingProduct]
    rows: list[LogisticsRow]
