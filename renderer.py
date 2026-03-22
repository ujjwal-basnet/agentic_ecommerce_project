"""Renderer — TOOL_COMPONENT_MAP + SSE event builder."""

import json
from typing import Any

TOOL_COMPONENT_MAP: dict[str, str | None] = {
    "search_products_tool": "ProductList",
    "add_to_cart": "CartConfirmation",
    "view_cart": "CartDrawer",
    "remove_from_cart": "CartConfirmation",
    "update_cart": "CartDrawer",
    "clear_cart": "CartDrawer",
    "recommend": "RecommendGrid",
    "get_weather": "WeatherCard",
    "virtual_try_on": "TryOnResult",
    "get_analytics": None,
    "add_product": None,
    "get_inventory": None,
    "post_to_facebook": None,
}


def get_component(tool_name: str) -> str | None:
    return TOOL_COMPONENT_MAP.get(tool_name)


def make_sse_events(result: dict[str, Any], intent: str = "") -> list[dict[str, str]]:
    """Convert executor result → list of SSE event dicts."""
    events = []

    text = result.get("text") or "Here you go!"
    tool = result.get("tool")
    data = result.get("data")
    cart_count = result.get("cart_count", 0)

    events.append({
        "event": "message",
        "data": json.dumps({"type": "text", "content": text}),
    })

    component = (result.get("component") or get_component(tool)) if tool else None
    if component and data is not None and data != [] and data != {}:
        events.append({
            "event": "message",
            "data": json.dumps({
                "type": "tool_result",
                "component": component,
                "tool": tool,
                "data": data,
            }),
        })

    events.append({
        "event": "message",
        "data": json.dumps({"type": "cart_sync", "cart_count": cart_count}),
    })

    return events


def render_for_api(result: dict[str, Any]) -> dict[str, Any]:
    """Non-streaming API response format."""
    tool = result.get("tool")
    return {
        "text": result.get("text", ""),
        "component": get_component(tool) if tool else result.get("component"),
        "tool": tool,
        "data": result.get("data"),
        "cart_count": result.get("cart_count", 0),
    }
