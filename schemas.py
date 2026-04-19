"""Shared Pydantic schemas for API routes, planner output, and agent data."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base model that tolerates existing DB rows with extra columns."""

    model_config = ConfigDict(extra="allow")

# ── Engine / LLM orchestration ────────────────────────────────────────────────


class ToolCall(APIModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(APIModel):
    tool: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class QueryResolution(APIModel):
    needs_context: bool = False
    rewritten_query: str = ""


class PlannerOutput(APIModel):
    intent: Literal[
        "smalltalk",
        "shopping",
        "cart",
        "weather",
        "tryon",
        "other",
        "fallback",
        "general",
    ] = "general"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    direct_response: str | None = None


class ResponseGeneratorOutput(APIModel):
    text: str
    component: Literal[
        "ProductList",
        "CartDrawer",
        "CartConfirmation",
        "RecommendGrid",
        "WeatherCard",
    ] | None = None


# ── Common route responses ───────────────────────────────────────────────────


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


class ChatEvent(APIModel):
    type: Literal["text", "tool_result", "cart_sync", "image", "error"]
    content: str | None = None
    component: str | None = None
    data: dict[str, Any] | None = None
    products: list[dict[str, Any]] | None = None
    cart_count: int | None = None
    image_path: str | None = None


# ── Owner route responses ────────────────────────────────────────────────────


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


class StatusUpdateResponse(APIModel):
    ok: bool
    order_id: int
    status: str


class UserSchema(APIModel):
    id: int
    name: str
    email: str


class LoginResponse(APIModel):
    ok: bool
    user: UserSchema


class MeResponse(APIModel):
    user: UserSchema | None = None


class TrackViewResponse(APIModel):
    ok: bool


class ProductCreateResponse(APIModel):
    success: bool
    product_id: int


class ProductDeleteResponse(APIModel):
    ok: bool


class ProductUpdateResponse(APIModel):
    success: bool


class SocialPostResponse(APIModel):
    status: str | None = None
    success: bool | None = None
    message: str | None = None
    id: str | None = None


# ── Specialist responses ─────────────────────────────────────────────────────


class TryOnResponse(APIModel):
    success: bool | None = None
    image_path: str | None = None
    message: str | None = None
    error: str | None = None


# ── Campaign workflow (Curator AI) ───────────────────────────────────────────

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
