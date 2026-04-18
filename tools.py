"""LangChain tool functions for SmartShop — pure Python callables."""

from __future__ import annotations

import json
import logging

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
        products = []
        missing = []
        for pid in product_ids:
            p = database.get_product_by_id(int(pid))
            if not p:
                missing.append(int(pid))
                continue
            products.append({
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
def get_user_history(session_id: str, limit: int = 5) -> str:
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


@tool
def get_user_preferences(session_id: str) -> str:
    """Get user preferences based on order/cart history."""
    try:
        orders = database.get_orders_by_session(session_id, limit=10)
        cart = database.db_get_cart(session_id)
        # Derive preferences from what user has bought/carted
        categories = [o.get("category", "") for o in orders if o.get("category")]
        return json.dumps({
            "preferences": {
                "recent_categories": list(set(categories))[:5],
                "order_count": len(orders),
                "has_cart_items": len(cart) > 0,
            }
        })
    except Exception:
        logger.exception("get_user_preferences failed")
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

@tool
def check_try_on_eligible(
    product_id: int | None = None,
    product_name: str | None = None,
) -> str:
    """Check if a product is eligible for virtual try-on. Prefer product_id."""
    try:
        prod = None
        if product_id is not None:
            prod = database.get_product_by_id(int(product_id))
        if prod is None and product_name:
            prod = database.get_product_by_name(product_name)
            if prod is None:
                products = database.search_products(product_name, limit=5)
                prod = next((p for p in products if p.get("is_wearable")), None) or (products[0] if products else None)

        if not prod:
            ref = f"id={product_id}" if product_id is not None else f"'{product_name}'"
            return json.dumps({"eligible": False, "error": f"Product {ref} not found"})

        is_wearable = bool(prod.get("is_wearable", 0))
        return json.dumps({
            "eligible": is_wearable,
            "product_id": prod.get("id"),
            "product_name": prod.get("name"),
            "reason": "Wearable item" if is_wearable else "Not a wearable item",
        })
    except Exception:
        logger.exception("check_try_on_eligible failed")
        raise


@tool
def perform_virtual_try_on(product_id: int, user_image_path: str) -> str:
    """Perform virtual try-on — composes the user's photo with the product via Gemini image model."""
    try:
        from pathlib import Path
        import uuid

        if not user_image_path or not Path(user_image_path).exists():
            return json.dumps({
                "success": False,
                "error": "User photo not found. Please upload a photo first.",
            })

        product = database.get_product_by_id(product_id)
        if not product:
            return json.dumps({"success": False, "error": f"Product #{product_id} not found"})

        product_image_path = product.get("image_path", "")
        if not product_image_path or not Path(product_image_path).exists():
            return json.dumps({"success": False, "error": f"No image for '{product['name']}'"})

        from google import genai
        from google.oauth2 import service_account
        from PIL import Image

        if config.GOOGLE_GENAI_USE_VERTEXAI:
            creds = service_account.Credentials.from_service_account_file(
                str(Path(config.GOOGLE_APPLICATION_CREDENTIALS).expanduser()),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            client = genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION,
                credentials=creds,
            )
        else:
            client = genai.Client(api_key=config.GOOGLE_API_KEY)

        user_img = Image.open(user_image_path)
        product_img = Image.open(product_image_path)

        category = (product.get("category") or "").lower()
        name = product.get("name") or "product"
        color = product.get("color") or ""
        if any(k in category for k in ("shirt", "tshirt", "t-shirt", "top", "jacket", "hoodie", "sweater", "dress")):
            action = "wearing the garment on their torso"
        elif any(k in category for k in ("pant", "trouser", "jean", "short", "skirt")):
            action = "wearing the garment on their lower body"
        elif any(k in category for k in ("shoe", "sneaker", "boot", "sandal")):
            action = "wearing the footwear"
        elif any(k in category for k in ("watch", "bracelet", "ring", "necklace", "jewel")):
            action = "wearing the accessory"
        elif any(k in category for k in ("hat", "cap", "beanie")):
            action = "wearing the headwear"
        elif any(k in category for k in ("bag", "purse", "backpack")):
            action = "holding or wearing the bag"
        elif any(k in category for k in ("glass", "sunglass", "eyewear")):
            action = "wearing the eyewear"
        else:
            action = "using or wearing the product naturally"

        prompt = (
            f"Compose a photorealistic virtual try-on image. Show the exact same person from the USER reference "
            f"{action} — specifically the {color + ' ' if color else ''}{name} from the PRODUCT reference. "
            "Preserve the person's face, skin tone, hair, body proportions, pose, and background as closely as "
            "possible. Replace or overlay only the relevant clothing/item area with the product, matching "
            "realistic fabric drape, lighting, and shadows. Output a single clean photograph, no text, no "
            "watermarks, no collage."
        )

        response = client.models.generate_content(
            model=config.NANO_BANANA_MODEL,
            contents=[prompt, user_img, product_img],
        )

        output_dir = Path(config.TRYON_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"tryon_{uuid.uuid4().hex[:8]}.png"

        for cand in response.candidates or []:
            parts = getattr(cand.content, "parts", []) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    out_path.write_bytes(inline.data)
                    return json.dumps({
                        "success": True,
                        "image_path": str(out_path),
                        "message": f"Try-on generated for {name}",
                        "model": config.NANO_BANANA_MODEL,
                    })

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
    get_user_preferences,
]

WEATHER_TOOLS = [
    get_weather,
]

TRY_ON_TOOLS = [
    check_try_on_eligible,
    perform_virtual_try_on,
]

ALL_TOOLS = PRODUCT_TOOLS + CART_TOOLS + CONTEXT_TOOLS + WEATHER_TOOLS + TRY_ON_TOOLS
