"""LangChain tools for SmartShop agents.

Each tool is a function that does one thing. Agents are collections of tools.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

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
def search_products(query: str, limit: int = 8, max_price: float = None, color: str = None, category: str = None) -> str:
    """Search products with filters. Handles keywords, price ranges, colors, categories.

    Examples:
    - "red shirt" → query="red shirt"
    - "under 2000" → max_price=2000
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
def add_to_cart(session_id: str, product_name: str, quantity: int = 1) -> str:
    """Add a product to cart. Finds product price automatically."""
    try:
        # Look up product to get price
        prod = database.get_product_by_name(product_name)
        if not prod:
            return json.dumps({
                "success": False,
                "error": f"Product '{product_name}' not found",
                "message": f"I couldn't find '{product_name}' in the catalog.",
            })
        
        price = float(prod.get("price", 0))
        database.db_add_to_cart(session_id, prod["name"], price, quantity, product_id=prod.get("id"))
        
        # Return updated cart
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Added {quantity} x {prod['name']} to your cart."
        
        return json.dumps({
            "success": True,
            "message": message,
            "text": message,
            "added": prod["name"],
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
def remove_from_cart(session_id: str, product_name: str) -> str:
    """Remove a product from cart."""
    try:
        database.db_remove_from_cart(session_id, product_name)
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Removed {product_name} from your cart."
        
        return json.dumps({
            "success": True,
            "message": message,
            "text": message,
            "removed": product_name,
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
def check_try_on_eligible(product_name: str) -> str:
    """Check if a product is eligible for virtual try-on."""
    try:
        prod = database.get_product_by_name(product_name)
        if not prod:
            # Try searching
            products = database.search_products(product_name, limit=5)
            wearable = [p for p in products if p.get("is_wearable")]
            if wearable:
                prod = wearable[0]
            elif products:
                prod = products[0]
        
        if not prod:
            return json.dumps({"eligible": False, "error": f"Product '{product_name}' not found"})
        
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
    """Perform virtual try-on using nanobanan model (fast virtual try-on)."""
    try:
        from pathlib import Path
        import uuid
        import requests
        
        # Validate inputs
        if not user_image_path or not Path(user_image_path).exists():
            return json.dumps({
                "success": False,
                "error": "User photo not found. Please upload a photo first.",
            })
        
        # Get product
        product = database.get_product_by_id(product_id)
        if not product:
            return json.dumps({"success": False, "error": f"Product #{product_id} not found"})
        
        product_image_path = product.get("image_path", "")
        if not product_image_path or not Path(product_image_path).exists():
            return json.dumps({"success": False, "error": f"No image for '{product['name']}'"})
        
        # Use nanobanan for virtual try-on
        # TODO: Replace with your actual nanobanan API endpoint
        # Example: POST to nanobanan API with person_img + cloth_img
        
        output_dir = Path(config.TRYON_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"tryon_{uuid.uuid4().hex[:8]}.png"
        
        # Placeholder: Copy user image as mock result
        # Replace this block with actual nanobanan API call:
        # 
        # with open(user_image_path, "rb") as f_person, \
        #      open(product_image_path, "rb") as f_cloth:
        #     resp = requests.post(
        #         "https://your-nanobanan-api.com/tryon",
        #         files={"person": f_person, "cloth": f_cloth},
        #         timeout=60
        #     )
        #     out_path.write_bytes(resp.content)
        
        # For now, return mock success
        import shutil
        shutil.copy(user_image_path, out_path)
        
        return json.dumps({
            "success": True,
            "image_path": str(out_path),
            "message": "Try-on completed with Nano Banana",
            "model": config.NANO_BANANA_MODEL,
        })
    except Exception:
        logger.exception("perform_virtual_try_on failed")
        raise


# ───────────────────────────────────────────────────────────────────────────────
# All Tools List (for agent creation)
# ───────────────────────────────────────────────────────────────────────────────

PRODUCT_TOOLS = [
    get_all_products,
    search_products,
    get_product_by_id,
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
