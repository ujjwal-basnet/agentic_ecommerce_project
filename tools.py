"""LangChain tool functions for SmartShop — pure Python callables."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from langchain_core.tools import tool

import analytics_ml
import database
import config

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────────────
# Product / Search Tools
# ───────────────────────────────────────────────────────────────────────────────

@tool
def get_all_products() -> str:
    """Get all products from the database. Returns JSON string of product list."""
    try:
        products = database.get_all_products()
        # Clean up for LLM consumption
        cleaned = []
        for p in products:
            cleaned.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "color": p.get("color"),
                "price": float(p.get("price", 0)),
                "quantity": int(p.get("quantity", 0)),
                "description": p.get("description", ""),
                "image_path": p.get("image_path", ""),
                "is_wearable": bool(p.get("is_wearable", 0)),
            })
        return json.dumps({"products": cleaned, "count": len(cleaned)})
    except Exception:
        logger.exception("get_all_products failed")
        raise


@tool
def search_products(
    query: str = "",
    limit: int = 8,
    max_price: float | None = None,
    color: str | None = None,
    category: str | None = None,
) -> str:
    """Search products with optional filters. All params optional — empty query returns all in-stock products, then filters apply.

    Examples:
    - "red shirt" → query="red shirt"
    - "under 2000" → max_price=2000  (no query needed)
    - "red shirt under 2000" → query="red shirt", max_price=2000
    """
    try:
        results = database.search_products(query, limit=limit)

        # Apply extra filters the database function doesn't handle
        if max_price is not None:
            results = [p for p in results if float(p.get("price", 0)) <= max_price]
        if color:
            results = [p for p in results if color.lower() in str(p.get("color", "")).lower()]
        if category:
            results = [p for p in results if category.lower() in str(p.get("category", "")).lower()]

        cleaned = []
        for p in results[:limit]:
            cleaned.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "color": p.get("color"),
                "price": float(p.get("price", 0)),
                "quantity": int(p.get("quantity", 0)),
                "description": p.get("description", "")[:100],
                "image_path": p.get("image_path", ""),
                "is_wearable": bool(p.get("is_wearable", 0)),
            })

        return json.dumps({"products": cleaned, "query": query, "count": len(cleaned)})
    except Exception:
        logger.exception("search_products failed")
        raise


@tool
def get_product_by_id(product_id: int) -> str:
    """Get detailed info for a specific product by ID."""
    try:
        p = database.get_product_by_id(product_id)
        if not p:
            return json.dumps({"error": f"Product {product_id} not found"})
        return json.dumps({
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "color": p.get("color"),
            "price": float(p.get("price", 0)),
            "quantity": int(p.get("quantity", 0)),
            "description": p.get("description", ""),
            "image_path": p.get("image_path", ""),
            "is_wearable": bool(p.get("is_wearable", 0)),
        })
    except Exception:
        logger.exception("get_product_by_id failed")
        raise


@tool
def get_products_by_ids(product_ids: list[int]) -> str:
    """Fetch full DB records for a list of product IDs. Use this when the planner
    already picked specific products from the catalog. Returns {products: [...]}."""
    try:
        ids = [int(pid) for pid in product_ids]
        rows = database.get_products_by_ids(ids)
        found_ids = {p["id"] for p in rows}
        missing = [i for i in ids if i not in found_ids]
        products = [{
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "color": p.get("color"),
            "price": float(p.get("price", 0)),
            "quantity": int(p.get("quantity", 0)),
            "description": p.get("description", ""),
            "image_path": p.get("image_path", ""),
            "is_wearable": bool(p.get("is_wearable", 0)),
        } for p in rows]
        return json.dumps({"products": products, "count": len(products), "missing": missing})
    except Exception:
        logger.exception("get_products_by_ids failed")
        raise


@tool
def get_products_by_category(category: str) -> str:
    """Get all products in a specific category."""
    try:
        all_products = database.get_all_products()
        products = [p for p in all_products if category.lower() in str(p.get("category", "")).lower()]
        cleaned = []
        for p in products:
            cleaned.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "color": p.get("color"),
                "price": float(p.get("price", 0)),
                "quantity": int(p.get("quantity", 0)),
                "image_path": p.get("image_path", ""),
                "is_wearable": bool(p.get("is_wearable", 0)),
            })
        return json.dumps({"products": cleaned, "category": category, "count": len(cleaned)})
    except Exception:
        logger.exception("get_products_by_category failed")
        raise


# ───────────────────────────────────────────────────────────────────────────────
# Cart Tools
# ───────────────────────────────────────────────────────────────────────────────

@tool
def view_cart(session_id: str) -> str:
    """View the current cart for a session. Returns cart items and total."""
    try:
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        
        return json.dumps({
            "items": cart,
            "count": count,
            "total": total,
            "is_empty": len(cart) == 0,
            "text": "Your cart is empty." if not cart else f"Your cart has {count} item(s), totaling Rs. {total}.",
        })
    except Exception:
        logger.exception("view_cart failed")
        raise


@tool
def add_to_cart(
    session_id: str,
    product_id: int | None = None,
    product_name: str | None = None,
    quantity: int = 1,
) -> str:
    """Add a product to cart. Prefer product_id (from Catalog); product_name is a fallback."""
    try:
        prod = None
        if product_id is not None:
            prod = database.get_product_by_id(int(product_id))
        if prod is None and product_name:
            prod = database.get_product_by_name(product_name)
        if not prod:
            ref = f"id={product_id}" if product_id is not None else f"'{product_name}'"
            return json.dumps({
                "success": False,
                "error": f"Product {ref} not found",
                "message": f"I couldn't find that product ({ref}) in the catalog.",
            })

        price = float(prod.get("price", 0))
        database.db_add_to_cart(session_id, prod["name"], price, quantity, product_id=prod.get("id"))
        analytics_ml.invalidate_cache()

        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Added {quantity} x {prod['name']} to your cart."

        return json.dumps({
            "success": True,
            "message": message,
            "text": message,
            "added": prod["name"],
            "product_id": prod.get("id"),
            "price": price,
            "image_path": prod.get("image_path", ""),
            "quantity": quantity,
            "count": count,
            "total": total,
            "cart_count": count,
            "cart_total": total,
            "cart_total_items": count,
            "cart_total_price": total,
        })
    except Exception:
        logger.exception("add_to_cart failed")
        raise


@tool
def remove_from_cart(
    session_id: str,
    product_id: int | None = None,
    product_name: str | None = None,
) -> str:
    """Remove a product from cart. Prefer product_id (from Catalog); product_name is a fallback."""
    try:
        removed_name = product_name
        if product_id is not None:
            prod = database.get_product_by_id(int(product_id))
            if prod:
                removed_name = prod["name"]

        if not removed_name:
            return json.dumps({
                "success": False,
                "error": "No product_id or product_name provided",
                "message": "I need to know which product to remove.",
            })

        database.db_remove_from_cart(session_id, removed_name)
        analytics_ml.invalidate_cache()
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Removed {removed_name} from your cart."

        return json.dumps({
            "success": True,
            "message": message,
            "text": message,
            "removed": removed_name,
            "product_id": product_id,
            "count": count,
            "total": total,
            "cart_count": count,
            "cart_total": total,
            "cart_total_items": count,
            "cart_total_price": total,
        })
    except Exception:
        logger.exception("remove_from_cart failed")
        raise


@tool
def clear_cart(session_id: str) -> str:
    """Clear all items from cart."""
    try:
        database.db_clear_cart(session_id)
        return json.dumps({
            "success": True,
            "message": "Cart cleared.",
            "text": "Cart cleared.",
            "count": 0,
            "total": 0,
            "cart_count": 0,
            "cart_total": 0,
            "cart_total_items": 0,
            "cart_total_price": 0,
        })
    except Exception:
        logger.exception("clear_cart failed")
        raise


# ───────────────────────────────────────────────────────────────────────────────
# User History / Context Tools
# ───────────────────────────────────────────────────────────────────────────────

@tool
def get_user_history(session_id: str, limit: int = 6) -> str:
    """Get recent conversation history for a user session."""
    try:
        history = database.load_history(session_id, limit=limit)
        # Return just the essential info
        simplified = []
        for h in history:
            simplified.append({
                "role": h.get("role"),
                "content": h.get("content", "")[:200],  # Truncate long messages
                "timestamp": h.get("timestamp"),
            })
        return json.dumps({"history": simplified, "session_id": session_id})
    except Exception:
        logger.exception("get_user_history failed")
        raise


# ───────────────────────────────────────────────────────────────────────────────
# Weather Tools
# ───────────────────────────────────────────────────────────────────────────────

@tool
def get_weather(location: str = "Kathmandu") -> str:
    """Get current weather for a location."""
    try:
        if not config.OPENWEATHER_API_KEY:
            # Return mock data if no API key
            import random
            conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain"]
            temp = round(random.uniform(15, 35), 1)
            return json.dumps({
                "location": location,
                "temperature": temp,
                "feels_like": round(temp + random.uniform(-2, 2), 1),
                "humidity": random.randint(30, 90),
                "weather": random.choice(conditions),
                "source": "mock",
            })
        
        import requests
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = requests.get(url, params={
            "q": location, 
            "appid": config.OPENWEATHER_API_KEY,
            "units": "metric",
        }, timeout=10)
        resp.raise_for_status()
        d = resp.json()
        
        return json.dumps({
            "location": d.get("name", location),
            "temperature": round(d["main"]["temp"], 1),
            "feels_like": round(d["main"]["feels_like"], 1),
            "humidity": d["main"]["humidity"],
            "weather": d["weather"][0]["description"].title() if d.get("weather") else "Clear",
            "source": "openweather",
        })
    except Exception:
        logger.exception("get_weather failed")
        raise


# ───────────────────────────────────────────────────────────────────────────────
# Try-On Tools
# ───────────────────────────────────────────────────────────────────────────────

_TRYON_PROMPT = (
    "Compose a single photorealistic image of the person in the USER reference "
    "actually wearing or using the ITEM shown in the product reference. "
    "Place the item on the correct body region; match scale, perspective, drape, "
    "and fabric physics; match the scene's lighting, shadows, and skin tone. "
    "Keep the person's face, body proportions, and background unchanged. "
    "No text overlays, no watermarks, no extra items. Output one image only."
)


@tool
def perform_virtual_try_on(product_id: int, user_image_path: str) -> str:
    """Virtual try-on via Gemini image model. Only runs for products the owner flagged as wearable."""
    try:
        if not user_image_path or not Path(user_image_path).exists():
            return json.dumps({
                "success": False,
                "error": "User photo not found. Please upload a photo first.",
            })

        product = database.get_product_by_id(product_id)
        if not product:
            return json.dumps({"success": False, "error": f"Product #{product_id} not found"})

        if not product.get("is_wearable"):
            return json.dumps({
                "success": False,
                "error": f"'{product['name']}' is not marked as wearable. Only owner-flagged wearables can be tried on.",
            })

        product_image_path = product.get("image_path", "")
        if not product_image_path or not Path(product_image_path).exists():
            return json.dumps({"success": False, "error": f"No image for '{product['name']}'"})

        from PIL import Image
        from google_client import get_genai_client
        import storage as _storage

        try:
            client = get_genai_client()
        except Exception as e:
            logger.exception("Try-on: Google credentials failed")
            return json.dumps({"success": False, "error": f"Credentials failed: {e}"})

        user_img = Image.open(user_image_path)
        product_img = Image.open(product_image_path)

        response = client.models.generate_content(
            model=config.GEMINI_IMAGE_MODEL,
            contents=[_TRYON_PROMPT, product_img, user_img],
        )

        output_dir = Path(config.TRYON_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = f"tryon_{uuid.uuid4().hex[:8]}.png"

        text_parts: list[str] = []
        for cand in response.candidates or []:
            parts = getattr(cand.content, "parts", []) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    url = _storage.upload("tryon-results", fname, inline.data)
                    if url:
                        img_result = url
                    else:
                        out_path = output_dir / fname
                        out_path.write_bytes(inline.data)
                        img_result = str(out_path)
                    return json.dumps({
                        "success": True,
                        "image_path": img_result,
                        "message": f"Try-on generated for {product['name']}",
                        "model": config.GEMINI_IMAGE_MODEL,
                    })
                text = getattr(part, "text", None)
                if text:
                    text_parts.append(text)

        # Model returned only text — log it so we know what went wrong.
        if text_parts:
            logger.warning("Try-on returned text only (no image): %s", " | ".join(text_parts)[:500])
        return json.dumps({
            "success": False,
            "error": "Image model returned no image data. Try a different photo.",
        })
    except Exception as e:
        logger.exception("perform_virtual_try_on failed")
        return json.dumps({"success": False, "error": f"Try-on failed: {e}"})


# ───────────────────────────────────────────────────────────────────────────────
# All Tools List (for agent creation)
# ───────────────────────────────────────────────────────────────────────────────

PRODUCT_TOOLS = [
    get_all_products,
    search_products,
    get_product_by_id,
    get_products_by_ids,
    get_products_by_category,
]

CART_TOOLS = [
    view_cart,
    add_to_cart,
    remove_from_cart,
    clear_cart,
]

CONTEXT_TOOLS = [
    get_user_history,
]

WEATHER_TOOLS = [
    get_weather,
]

TRY_ON_TOOLS = [
    perform_virtual_try_on,
]

ALL_TOOLS = PRODUCT_TOOLS + CART_TOOLS + CONTEXT_TOOLS + WEATHER_TOOLS + TRY_ON_TOOLS
