"""SmartShop MCP Connector — exposes the entire agent system as a standard MCP server.

This connector packages SmartShop's agents, orchestrator, and planner into
FastMCP tools so ANY MCP client (ChatGPT, Claude, Facebook Messenger, custom
bots) can interact with the shop via pure text — no images, no UI components.

Architecture:
    External Client  ←→  connector.py (FastMCP)  ←→  Internal Agents / DB
                         ↑ text-only MCP I/O       ↑ custom MCP (mcp.py)

Run:
    python connector.py                    # stdio (for Claude Desktop, etc.)
    python connector.py --transport sse    # SSE  (for remote HTTP clients)

Or use from code:
    from fastmcp import Client
    async with Client("connector.py") as c:
        result = await c.call_tool("chat", {"message": "show me red shirts"})
"""

from __future__ import annotations

import json
import uuid
import logging
from pathlib import Path

from fastmcp import FastMCP

# ── Bootstrap the SmartShop backend ────────────────────────────────────────
import config          # loads .env
import database        # DB helpers

from channels.capabilities import MCP

database.init_db()

_log = logging.getLogger("smartshop.connector")

# ---------------------------------------------------------------------------
#  FastMCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "SmartShop",
    instructions=(
        "SmartShop is an AI-powered e-commerce assistant. "
        "Use the `chat` tool for natural language shopping queries. "
        "Or call individual tools directly: search_products, add_to_cart, "
        "view_cart, remove_from_cart, clear_cart, get_recommendations, "
        "get_weather, checkout. All responses are text-only."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  RESOURCES — static data an LLM can read for grounding
# ═══════════════════════════════════════════════════════════════════════════

@mcp.resource("smartshop://catalog")
def catalog_resource() -> str:
    """Full product catalog as markdown — useful for grounding product queries."""
    catalog_path = Path("product_description.md")
    if catalog_path.exists():
        return catalog_path.read_text()
    # Fallback: build from DB
    products = database.get_all_products()
    lines = ["# SmartShop Product Catalog\n"]
    for p in products:
        lines.append(
            f"- **{p['name']}** | {p.get('category','')} | {p.get('color','')} "
            f"| Rs.{p.get('price',0)} | Stock: {p.get('quantity',0)}"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  TOOLS — text-only wrappers around the internal agents
# ═══════════════════════════════════════════════════════════════════════════

# ── 1. Chat (orchestrator + planner) ──────────────────────────────────────

@mcp.tool
def chat(message: str, session_id: str = "") -> str:
    """Send a natural-language message to SmartShop.

    The orchestrator classifies intent, builds a plan, executes it through
    the internal agents, and returns a text summary. Handles: product search,
    cart operations, recommendations, weather, and general chitchat.

    Args:
        message: The user's message (e.g. "show me red shirts", "add to cart")
        session_id: Optional session ID for cart persistence. Auto-generated if empty.

    Returns:
        Text response from SmartShop.
    """
    from orchestrator import classify_intent, build_plan
    from executor import execute_plan
    from llm import call_llm

    if not session_id:
        session_id = f"mcp_{uuid.uuid4().hex[:8]}"

    # 1. Classify intent
    context = _get_recent_context(session_id)
    intent = classify_intent(message, context)
    _log.info("chat intent=%s message=%s", intent, message[:80])

    # 2. Build plan with MCP channel capabilities
    plan = build_plan(message, intent, mcp=True, channel_caps=MCP)

    # 3. If no plan (chitchat / tryon), use LLM directly
    if not plan:
        if config.openai_enabled():
            reply = call_llm(
                "You are SmartShop, a friendly e-commerce assistant. "
                "Answer briefly. If the user asks about try-on, explain that "
                "virtual try-on is available in the SmartShop web app.",
                message,
                temperature=0.7,
            )
            database.save_message(session_id, "user", message)
            database.save_message(session_id, "assistant", reply)
            return reply
        return "I'm SmartShop, your shopping assistant! Try asking about products, recommendations, or your cart."

    # 4. Execute plan with MCP channel capabilities
    result = execute_plan(
        plan=plan,
        session_id=session_id,
        user_input=message,
        channel_caps=MCP,
    )

    # 5. Format text-only response using renderer (consistent with web)
    from renderer import render_for_api
    rendered = render_for_api(result, mode="text")
    return rendered.get("text", "Here you go!")


# ── 2. Search Products ────────────────────────────────────────────────────

@mcp.tool
def search_products(query: str) -> str:
    """Search the SmartShop product catalog.

    Args:
        query: Search terms (e.g. "red tshirt", "dress under 100", "sunglasses")

    Returns:
        Formatted list of matching products with name, category, color, price, stock.
    """
    products = database.search_products(query, limit=10)
    if not products:
        return f"No products found for '{query}'."

    lines = [f"Found {len(products)} product(s):\n"]
    for p in products:
        stock = int(p.get("quantity", 0))
        stock_label = f"In stock ({stock})" if stock > 0 else "Out of stock"
        lines.append(
            f"  • {p['name']} — Rs.{p.get('price', 0)} "
            f"[{p.get('category', '')}] [{p.get('color', '')}] "
            f"({stock_label})"
        )
    return "\n".join(lines)


# ── 3. Cart Operations ────────────────────────────────────────────────────

@mcp.tool
def add_to_cart(session_id: str, product_name: str, quantity: int = 1) -> str:
    """Add a product to the shopping cart.

    Args:
        session_id: Session ID for the user
        product_name: Name of the product (e.g. "Red T-Shirt")
        quantity: How many to add (default 1)

    Returns:
        Confirmation message with updated cart summary.
    """
    product = database.get_product_by_name(product_name)
    if not product:
        return f"Product '{product_name}' not found in catalog."

    database.db_add_to_cart(session_id, product["name"], float(product["price"]), quantity)
    cart = database.db_get_cart(session_id)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    total = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
    return f"Added {quantity}x {product['name']} (Rs.{product['price']}) to cart. Cart: {count} items, Rs.{total}"


@mcp.tool
def view_cart(session_id: str) -> str:
    """View all items currently in the shopping cart.

    Args:
        session_id: Session ID for the user

    Returns:
        List of cart items with quantities and total.
    """
    cart = database.db_get_cart(session_id)
    if not cart:
        return "Your cart is empty."

    lines = ["Your cart:\n"]
    total = 0.0
    for item in cart:
        qty = int(item["quantity"])
        price = float(item["price"])
        subtotal = qty * price
        total += subtotal
        lines.append(f"  • {item['product_name']} — {qty}x Rs.{price} = Rs.{subtotal}")

    count = sum(int(i["quantity"]) for i in cart)
    lines.append(f"\nTotal: {count} item(s), Rs.{round(total, 2)}")
    return "\n".join(lines)


@mcp.tool
def remove_from_cart(session_id: str, product_name: str) -> str:
    """Remove a product from the shopping cart.

    Args:
        session_id: Session ID for the user
        product_name: Name of the product to remove

    Returns:
        Confirmation message.
    """
    database.db_remove_from_cart(session_id, product_name)
    return f"Removed '{product_name}' from cart."


@mcp.tool
def clear_cart(session_id: str) -> str:
    """Remove all items from the shopping cart.

    Args:
        session_id: Session ID for the user

    Returns:
        Confirmation message.
    """
    database.db_clear_cart(session_id)
    return "Cart cleared."


# ── 4. Checkout ───────────────────────────────────────────────────────────

@mcp.tool
def checkout(session_id: str) -> str:
    """Place an order for all items in the cart.

    Args:
        session_id: Session ID for the user

    Returns:
        Order confirmation with order IDs, or message if cart is empty.
    """
    cart = database.db_get_cart(session_id)
    if not cart:
        return "Your cart is empty. Add some products first!"

    total = round(sum(float(i["price"]) * int(i["quantity"]) for i in cart), 2)
    count = sum(int(i["quantity"]) for i in cart)
    order_ids = database.place_order(session_id)

    if not order_ids:
        return "Checkout failed — please try again."

    items_summary = ", ".join(f"{i['product_name']} x{i['quantity']}" for i in cart)
    return (
        f"Order placed! 🎉\n"
        f"Order ID(s): {', '.join(str(oid) for oid in order_ids)}\n"
        f"Items: {items_summary}\n"
        f"Total: Rs.{total} ({count} item(s))\n"
        f"Status: Pending"
    )


# ── 5. Recommendations ───────────────────────────────────────────────────

@mcp.tool
def get_recommendations() -> str:
    """Get personalized product recommendations from SmartShop.

    Returns:
        List of recommended products with details.
    """
    products = database.get_all_products()
    in_stock = [p for p in products if int(p.get("quantity", 0)) > 0]
    if not in_stock:
        in_stock = products
    if not in_stock:
        return "No products available for recommendations."

    # Rank by stock + price diversity
    by_qty = sorted(in_stock, key=lambda x: int(x.get("quantity", 0)), reverse=True)
    recs = by_qty[:8]

    lines = [f"Here are {len(recs)} recommendations:\n"]
    for p in recs:
        lines.append(
            f"  • {p['name']} — Rs.{p.get('price', 0)} "
            f"[{p.get('category', '')}] [{p.get('color', '')}] "
            f"(Stock: {p.get('quantity', 0)})"
        )
    return "\n".join(lines)


# ── 6. Weather ────────────────────────────────────────────────────────────

@mcp.tool
def get_weather(location: str = "Kathmandu") -> str:
    """Get current weather for a location (useful for clothing suggestions).

    Args:
        location: City name (default: Kathmandu)

    Returns:
        Weather summary with temperature, humidity, and conditions.
    """
    import requests as req

    if config.OPENWEATHER_API_KEY:
        try:
            resp = req.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": location, "appid": config.OPENWEATHER_API_KEY, "units": "metric"},
                timeout=10,
            )
            resp.raise_for_status()
            d = resp.json()
            temp = round(d["main"]["temp"], 1)
            feels = round(d["main"]["feels_like"], 1)
            hum = d["main"]["humidity"]
            desc = d["weather"][0]["description"].title() if d.get("weather") else "Clear"
            wind = round(d.get("wind", {}).get("speed", 0), 1)
            return (
                f"Weather in {d.get('name', location)}: {desc}\n"
                f"Temperature: {temp}°C (feels like {feels}°C)\n"
                f"Humidity: {hum}%  |  Wind: {wind} m/s"
            )
        except Exception as e:
            return f"Could not fetch weather for {location}: {e}"
    else:
        return f"Weather API not configured. Please set OPENWEATHER_API_KEY."


# ── 7. Product Details ────────────────────────────────────────────────────

@mcp.tool
def get_product_details(product_name: str) -> str:
    """Get detailed information about a specific product.

    Args:
        product_name: Full or partial product name

    Returns:
        Product details including description, price, stock, and category.
    """
    product = database.get_product_by_name(product_name)
    if not product:
        return f"Product '{product_name}' not found."

    return (
        f"Product: {product['name']}\n"
        f"Category: {product.get('category', 'N/A')}\n"
        f"Color: {product.get('color', 'N/A')}\n"
        f"Price: Rs.{product.get('price', 0)}\n"
        f"Stock: {product.get('quantity', 0)} units\n"
        f"Description: {product.get('description', 'No description available.')}\n"
        f"Wearable: {'Yes' if product.get('is_wearable') else 'No'}"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PROMPTS — reusable prompt templates for LLM clients
# ═══════════════════════════════════════════════════════════════════════════

@mcp.prompt
def shopping_assistant() -> str:
    """System prompt for using SmartShop as a shopping assistant."""
    return (
        "You are connected to SmartShop, an e-commerce store selling clothing "
        "and accessories. Use the available tools to help users:\n"
        "- Use `chat` for natural language queries (it handles intent + planning)\n"
        "- Use `search_products` to find specific items\n"
        "- Use `add_to_cart` / `view_cart` / `remove_from_cart` for cart management\n"
        "- Use `get_recommendations` for product suggestions\n"
        "- Use `get_weather` for weather-based clothing advice\n"
        "- Use `checkout` to place orders\n\n"
        "All responses are text-only. Products include t-shirts, dresses, jackets, "
        "saris, sunglasses, and more. Prices are in Nepali Rupees (Rs.)."
    )


@mcp.prompt
def product_search_prompt(query: str) -> str:
    """Prompt template for product search queries."""
    return f"Search SmartShop for: {query}. Use the search_products tool with this query."


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _get_recent_context(session_id: str) -> str:
    """Get recent chat context for intent classification."""
    try:
        messages = database.get_messages(session_id, limit=6)
        if not messages:
            return ""
        lines = []
        for m in messages:
            role = m.get("role", "user")
            text = m.get("content", "")[:100]
            lines.append(f"{role}: {text}")
        return "\n".join(lines)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
