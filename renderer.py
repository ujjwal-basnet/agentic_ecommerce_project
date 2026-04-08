"""Renderer — TOOL_COMPONENT_MAP + SSE event builder.

Supports three interface modes so the same agent pipeline serves every client:
  - "web"       → rich UI components (ProductList, CartDrawer, …)
  - "text"      → plain text only (MCP clients, phone/voice calls)
  - "messaging" → text + image URLs (Facebook Messenger, WhatsApp, …)
"""

import json
from typing import Any

# ── Valid interface modes ─────────────────────────────────────────────────
VALID_MODES = ("web", "text", "messaging")

TOOL_COMPONENT_MAP: dict[str, str | None] = {
    "search_products_tool": "ProductList",
    "add_to_cart": "CartConfirmation",
    "view_cart": "CartDrawer",
    "remove_from_cart": "CartConfirmation",
    "update_cart": "CartDrawer",
    "clear_cart": "CartDrawer",
    "recommend": "RecommendGrid",
    "get_weather": "WeatherCard",
    "get_analytics": None,
    "add_product": None,
    "get_inventory": None,
    "post_to_facebook": None,
    "virtual_try_on": None,
}


def get_component(tool_name: str) -> str | None:
    return TOOL_COMPONENT_MAP.get(tool_name)


# ── Text formatters (used when mode != "web") ────────────────────────────

def _fmt_products(products: list[dict], include_images: bool = False) -> str:
    """Format a list of product dicts as a readable text list."""
    if not products:
        return ""
    lines = []
    for p in products:
        name = p.get("name") or p.get("product_name", "")
        price = p.get("price", "")
        cat = p.get("category", "")
        color = p.get("color", "")
        qty = p.get("quantity", "")
        img = p.get("image_path", "")
        parts = [f"  • {name}"]
        if price:
            parts.append(f"Rs.{price}")
        if cat:
            parts.append(f"[{cat}]")
        if color:
            parts.append(f"[{color}]")
        if qty:
            parts.append(f"(Stock: {qty})")
        line = " — ".join(parts[:2]) + (" " + " ".join(parts[2:]) if len(parts) > 2 else "")
        if include_images and img:
            line += f"\n    Image: {img}"
        lines.append(line)
    return "\n".join(lines)


def _fmt_cart(data: Any) -> str:
    """Format cart data (items list or dict with items key) as text."""
    items = data if isinstance(data, list) else (data.get("items", []) if isinstance(data, dict) else [])
    if not items:
        return ""
    lines = []
    total = 0.0
    for item in items:
        name = item.get("product_name") or item.get("name", "")
        qty = int(item.get("quantity", 1))
        price = float(item.get("price", 0))
        subtotal = qty * price
        total += subtotal
        lines.append(f"  • {name} — {qty}x Rs.{price} = Rs.{subtotal}")
    count = sum(int(i.get("quantity", 1)) for i in items)
    lines.append(f"  Total: {count} item(s), Rs.{round(total, 2)}")
    return "\n".join(lines)


def _fmt_data_as_text(component: str | None, data: Any, include_images: bool = False) -> str:
    """Convert component data → plain text based on component type."""
    if data is None or data == [] or data == {}:
        return ""

    if component in ("ProductList", "RecommendGrid"):
        products = data if isinstance(data, list) else (data.get("products", []) if isinstance(data, dict) else [])
        return _fmt_products(products, include_images=include_images)

    if component in ("CartDrawer", "CartConfirmation"):
        return _fmt_cart(data)

    if component == "WeatherCard":
        if isinstance(data, dict):
            parts = []
            if data.get("location"):
                parts.append(f"Weather in {data['location']}")
            if data.get("temperature"):
                parts.append(f"Temperature: {data['temperature']}°C")
            if data.get("description"):
                parts.append(data["description"])
            return "\n".join(parts) if parts else str(data)
        return str(data)

    # Fallback: dump as readable text
    if isinstance(data, dict):
        return "\n".join(f"  {k}: {v}" for k, v in data.items() if v)
    if isinstance(data, list):
        return _fmt_products(data, include_images=include_images)
    return str(data)


# ── SSE event builders ───────────────────────────────────────────────────

def make_sse_events(
    result: dict[str, Any],
    intent: str = "",
    mode: str = "web",
) -> list[dict[str, str]]:
    """Convert executor result → list of SSE event dicts.

    Args:
        result: executor output dict
        intent: classified intent string
        mode: "web" | "text" | "messaging"
    """
    if mode not in VALID_MODES:
        mode = "web"

    events = []
    text = result.get("text") or "Here you go!"
    tool = result.get("tool")
    data = result.get("data")
    cart_count = result.get("cart_count", 0)
    images = result.get("images")  # list of image paths (e.g. try-on output)

    component = (result.get("component") or get_component(tool)) if tool else None

    if mode == "web":
        # ── Web: text + rich component + inline images ──────────────
        events.append({
            "event": "message",
            "data": json.dumps({"type": "text", "content": text}),
        })

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

        # Inline images in chat (e.g. try-on results)
        if images:
            for img_path in images:
                events.append({
                    "event": "message",
                    "data": json.dumps({
                        "type": "image",
                        "image_path": img_path,
                    }),
                })

    else:
        # ── Text / Messaging: no components, data → text ────────────
        include_images = (mode == "messaging")

        extra = _fmt_data_as_text(component, data, include_images=include_images)
        full_text = f"{text}\n\n{extra}".strip() if extra else text

        events.append({
            "event": "message",
            "data": json.dumps({"type": "text", "content": full_text}),
        })

        # Images as separate events for messaging mode
        if include_images and images:
            for img_path in images:
                events.append({
                    "event": "message",
                    "data": json.dumps({
                        "type": "image",
                        "image_path": img_path,
                    }),
                })

    # Always emit cart_sync
    events.append({
        "event": "message",
        "data": json.dumps({"type": "cart_sync", "cart_count": cart_count}),
    })

    return events


def render_for_api(result: dict[str, Any], mode: str = "web") -> dict[str, Any]:
    """Non-streaming API response format."""
    if mode not in VALID_MODES:
        mode = "web"

    tool = result.get("tool")
    component = get_component(tool) if tool else result.get("component")

    if mode != "web":
        # Flatten to text
        text = result.get("text", "")
        include_images = (mode == "messaging")
        extra = _fmt_data_as_text(component, result.get("data"), include_images=include_images)
        full_text = f"{text}\n\n{extra}".strip() if extra else text
        return {
            "text": full_text,
            "component": None,
            "tool": tool,
            "data": result.get("data"),
            "images": result.get("images"),
            "cart_count": result.get("cart_count", 0),
        }

    return {
        "text": result.get("text", ""),
        "component": component,
        "tool": tool,
        "data": result.get("data"),
        "images": result.get("images"),
        "cart_count": result.get("cart_count", 0),
    }
