"""Core agent schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base model that tolerates existing DB rows with extra columns."""

    model_config = ConfigDict(extra="allow")


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
    component: (
        Literal[
            "ProductList",
            "CartDrawer",
            "CartConfirmation",
            "RecommendGrid",
            "WeatherCard",
        ]
        | None
    ) = None
