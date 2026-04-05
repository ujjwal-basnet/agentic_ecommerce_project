"""SearchAgent — LLM-augmented product search.

Flow:
1. Load product_description.md as catalog context.
2. Ask LLM which product IDs match the user query.
3. Fetch those products from the database.
4. If LLM is unavailable, fall back to SQL keyword search.
"""

import json
from pathlib import Path
from mcp import create_mcp_message
import database
import config

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "product_description.md"
_catalog_cache: str | None = None


def _load_catalog() -> str:
    global _catalog_cache
    if _catalog_cache is None:
        if _CATALOG_PATH.exists():
            _catalog_cache = _CATALOG_PATH.read_text(encoding="utf-8")
        else:
            _catalog_cache = ""
    return _catalog_cache


_SEARCH_SYSTEM = """You are a friendly shopping assistant for SmartShop.

Below is the COMPLETE product catalog:
---
{catalog}
---

{history_context}

The customer's query is given below. Your job:
1. Understand what the customer is asking — it could be a product search, a question about price, availability, color, category, price range, or anything product-related.
2. Use CONVERSATION HISTORY to resolve references like "show me", "that one", "it", "the one I asked about" etc. For example, if user previously asked about sari and now says "show me", they mean the sari.
3. Identify which products match or are relevant. Consider color, category, name, keywords, Nepali names, occasion, price range, and synonyms.
4. Be STRICT about color: if the user asks for "red tshirt", do NOT include blue or black t-shirts.
5. For BROAD queries like "all products", "everything", "what do you have", "what clothes", "show me all" → include ALL product IDs from the catalog.
6. For PRICE RANGE queries (e.g. "under 20", "below 50", "cheapest"):
   - Check the catalog prices carefully from the Quick Reference Table above.
   - "under X" means strictly less than X. Be mathematically precise!
   - Include ALL products that match the price condition.
7. Generate a SHORT, natural reply that DIRECTLY ANSWERS the user's question.
   - IMPORTANT: Do NOT list all products with prices. Product cards will be shown separately.
   - Keep it brief — 1-2 sentences max.
   - If they ask about price → mention the price: "The Black T-Shirt is Rs. 25!"
   - If they ask "under 20" → "Yes! The Sari is Rs. 10 — our most affordable item!"
   - If no match → be honest and tell what you DO have instead.
   - Do NOT enumerate products. Just answer naturally.
8. CRITICAL: If ANY products are relevant, you MUST include their IDs in the "ids" array. Never return empty ids if products exist that match.

Return ONLY valid JSON:
{{"ids": [3], "reply": "The Black T-Shirt is Rs. 25! Great casual everyday tee."}}
{{"ids": [1,2,3,4,5,6,7], "reply": "Here's everything we have! Take a look at our collection."}}
{{"ids": [], "reply": "We don't carry electronics, but we have great clothing and accessories!"}}
"""


class SearchAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, **kw) -> dict:
        content = msg.get("content", {})
        query = content.get("query", "")
        session_id = content.get("session_id", "")

        self._last_tool = "search_products_tool"

        # Build conversation history context for the LLM
        history_lines = []
        if session_id:
            import database
            history = database.load_history(session_id, limit=10)
            for h in history:
                role = h.get("role", "user")
                text = h.get("content", "")[:200]
                if text:
                    history_lines.append(f"{role}: {text}")

        try:
            items, reply = self._llm_search(query, history_lines)
            if items is None:
                items = self._sql_search(query)
                reply = ""

            if not reply:
                if items:
                    reply = f"Found {len(items)} product{'s' if len(items) != 1 else ''} matching your search!"
                else:
                    reply = f"Sorry, we don't have anything matching '{query}'. We carry t-shirts, dresses, jackets, sunglasses, and saris — let me know if any of those interest you!"

            if not items:
                return create_mcp_message("SearchAgent", {
                    "status": "ok",
                    "tool": self._last_tool,
                    "products": [],
                    "component": None,
                    "text": reply,
                })

            return create_mcp_message("SearchAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "products": items,
                "component": "ProductList",
                "text": reply,
            })

        except Exception as e:
            return create_mcp_message("SearchAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": "Search failed. Please try again.",
                "products": [],
                "component": None,
            })

    def _llm_search(self, query: str, history_lines: list[str] = None) -> tuple[list[dict] | None, str]:
        """Use LLM + product catalog to find matching product IDs, then fetch from DB.
        Returns (items, reply). items=None means LLM failed (fallback to SQL)."""
        if not config.openai_enabled():
            return None, ""

        catalog = _load_catalog()
        if not catalog:
            return None, ""

        try:
            from llm import call_llm_json
            history_context = ""
            if history_lines:
                history_context = "Recent conversation history (most recent first):\n" + "\n".join(history_lines)
            else:
                history_context = "No conversation history yet."
            system = _SEARCH_SYSTEM.format(catalog=catalog, history_context=history_context)
            result = call_llm_json(system, query)
            ids = result.get("ids", [])
            reply = result.get("reply", "")

            if not ids:
                return [], reply

            items = []
            for pid in ids:
                p = database.get_product_by_id(int(pid))
                if p and int(p.get("quantity", 0)) > 0:
                    items.append(self._format_product(p))
            return items, reply
        except Exception:
            return None, ""

    def _sql_search(self, query: str) -> list[dict]:
        """Fallback: pure SQL keyword search."""
        products = database.search_products(query, limit=8)
        return [self._format_product(p) for p in products]

    @staticmethod
    def _format_product(p: dict) -> dict:
        return {
            "id": p.get("id"),
            "name": p.get("name", ""),
            "category": p.get("category", ""),
            "color": p.get("color", ""),
            "price": float(p.get("price", 0)),
            "description": p.get("description", ""),
            "image_path": p.get("image_path", ""),
            "quantity": int(p.get("quantity", 0)),
            "is_wearable": bool(p.get("is_wearable", 0)),
        }
