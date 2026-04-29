"""Tool Registry — maps tool function names to callables + planner descriptions."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from api import config

logger = logging.getLogger(__name__)

_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "search_products": {"parallel_safe": True, "component": "ProductList"},
    "get_all_products": {
        "parallel_safe": True,
        "component": "RecommendGrid",
        "planner_visible": False,
    },
    "get_product_by_id": {
        "parallel_safe": True,
        "component": "ProductList",
        "planner_visible": False,
    },
    "get_products_by_ids": {"parallel_safe": True, "component": "ProductList"},
    "get_products_by_category": {
        "parallel_safe": True,
        "component": "ProductList",
        "planner_visible": False,
    },
    "view_cart": {"parallel_safe": True, "component": "CartDrawer"},
    "add_to_cart": {
        "parallel_safe": False,
        "component": "CartConfirmation",
        "writes": "cart",
    },
    "remove_from_cart": {
        "parallel_safe": False,
        "component": "CartConfirmation",
        "writes": "cart",
    },
    "clear_cart": {
        "parallel_safe": False,
        "component": "CartConfirmation",
        "writes": "cart",
    },
    "perform_virtual_try_on": {
        "parallel_safe": False,
        "component": None,
        "writes": "tryon",
    },
    "get_user_history": {
        "parallel_safe": True,
        "component": None,
        "planner_visible": False,
    },
    "search_knowledge_base": {"parallel_safe": True, "component": None},
}


def _format_product_catalog_from_db() -> str:
    from api import db

    products = db.get_all_products()
    if not products:
        return ""

    wearable_ids = [
        int(p["id"])
        for p in products
        if bool(p.get("is_wearable"))
        or str(p.get("category", "")).lower()
        in {"shirt", "tshirt", "t-shirt", "kurti", "jeans", "clothing"}
    ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        category = str(product.get("category") or "general").strip().title()
        grouped.setdefault(category, []).append(product)

    lines = [
        "# SmartShop Product Catalog",
        "",
        "Use the `id` to call `get_products_by_ids([...])`. All prices in Rs.",
    ]
    if wearable_ids:
        ids = ", ".join(str(pid) for pid in sorted(wearable_ids))
        lines.extend(
            [
                f"Clothing / wearable product IDs are {ids}.",
                "For wear, wearable, clothes, outfit, shirt, jeans, or kurti requests, prefer those IDs unless the user asks for a specific non-clothing item.",
            ]
        )
    lines.append("")

    for category in sorted(grouped):
        lines.append(f"## {category}")
        for product in sorted(grouped[category], key=lambda p: int(p.get("id") or 0)):
            name = str(product.get("name") or "").strip()
            color = str(product.get("color") or "").strip()
            price = float(product.get("price") or 0)
            tags = str(product.get("tags") or "").strip()
            parts = [
                f"- id={product.get('id')} · {name}",
                f"Rs. {price:g}",
            ]
            if color:
                parts.append(f"color: {color}")
            if tags and tags != "[]":
                parts.append(f"tags: {tags}")
            lines.append(" · ".join(parts))
        lines.append("")

    return "\n".join(lines).strip()


def _load_product_catalog() -> str:
    try:
        text = _format_product_catalog_from_db()
        if text:
            logger.info("Loaded product catalog from DB: %d chars", len(text))
            return text
    except Exception as exc:
        logger.warning("Could not load product catalog from DB: %s", exc)

    path = Path(config.PRODUCTS_MD_PATH)
    if not path.exists():
        logger.warning("products.md not found at %s", path)
        return ""
    text = path.read_text(encoding="utf-8").strip()
    logger.info("Loaded product catalog: %d chars", len(text))
    return text


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._descriptions: list[dict[str, Any]] = []
        self._metadata: dict[str, dict[str, Any]] = {}
        self._product_catalog: str = _load_product_catalog()
        self._register_all()

    def _register_all(self):
        from api.tools import (
            search_products,
            get_all_products,
            get_product_by_id,
            get_products_by_ids,
            get_products_by_category,
            view_cart,
            add_to_cart,
            remove_from_cart,
            clear_cart,
            perform_virtual_try_on,
            get_user_history,
            search_knowledge_base,
        )

        tool_defs = [
            {
                "name": "search_products",
                "fn": search_products,
                "description": "Search products by keyword and/or filters. All params optional.",
                "args": {
                    "query": "str (optional, default '') - keywords; omit for pure-filter queries like 'under 1000'",
                    "limit": "int (default 8)",
                    "max_price": "float (optional)",
                    "color": "str (optional)",
                    "category": "str (optional)",
                },
                "use_when": "Fallback keyword/filter search. Hidden from the planner because the DB-backed catalog is the product index.",
            },
            {
                "name": "get_all_products",
                "fn": get_all_products,
                "description": "Get ALL products from the store",
                "args": {},
                "use_when": "User asks for recommendations, wants to browse everything, or says 'show me everything'",
            },
            {
                "name": "get_product_by_id",
                "fn": get_product_by_id,
                "description": "Get a specific product by its ID number",
                "args": {"product_id": "int (required)"},
                "use_when": "User asks about one specific product by ID",
            },
            {
                "name": "get_products_by_ids",
                "fn": get_products_by_ids,
                "description": "Fetch full DB records for a list of product IDs",
                "args": {"product_ids": "list[int] (required) - IDs from the Catalog"},
                "use_when": "Preferred path when the Catalog already gave you the IDs. Bulk-fetch them to show in the UI.",
            },
            {
                "name": "get_products_by_category",
                "fn": get_products_by_category,
                "description": "Get all products in a specific category",
                "args": {"category": "str (required)"},
                "use_when": "User asks for all items in a category like 'show me all shirts'",
            },
            {
                "name": "add_to_cart",
                "fn": add_to_cart,
                "description": "Add a product to the shopping cart by ID (preferred) or name",
                "args": {
                    "session_id": "str (auto-injected)",
                    "product_id": "int (preferred) - pick from Catalog",
                    "product_name": "str (fallback)",
                    "quantity": "int (default 1)",
                },
                "use_when": "User says 'add to cart', 'buy this', 'I want this'. Always pass product_id when the Catalog gives it.",
            },
            {
                "name": "view_cart",
                "fn": view_cart,
                "description": "View current cart contents, items, and total",
                "args": {"session_id": "str (auto-injected)"},
                "use_when": "User says 'view cart', 'show cart', 'what's in my cart', 'my cart'",
            },
            {
                "name": "remove_from_cart",
                "fn": remove_from_cart,
                "description": "Remove a product from cart by ID (preferred) or name",
                "args": {
                    "session_id": "str (auto-injected)",
                    "product_id": "int (preferred) - pick from Catalog",
                    "product_name": "str (fallback)",
                },
                "use_when": "User says 'remove from cart', 'take out', 'delete from cart'. Always pass product_id when known.",
            },
            {
                "name": "clear_cart",
                "fn": clear_cart,
                "description": "Clear the entire shopping cart",
                "args": {"session_id": "str (auto-injected)"},
                "use_when": "User says 'clear cart', 'empty cart', 'remove everything'",
            },
            {
                "name": "perform_virtual_try_on",
                "fn": perform_virtual_try_on,
                "description": "Perform virtual try-on (checks eligibility automatically; requires user photo)",
                "args": {
                    "product_id": "int (required)",
                    "user_image_path": "str (auto-injected from upload)",
                },
                "use_when": "User wants to try on a product and has uploaded a photo. Tool handles eligibility check internally.",
            },
            {
                "name": "get_user_history",
                "fn": get_user_history,
                "description": "Get recent conversation history for personalization",
                "args": {"session_id": "str (auto-injected)"},
                "use_when": "Needed for personalized recommendations alongside get_all_products",
            },
            {
                "name": "search_knowledge_base",
                "fn": search_knowledge_base,
                "description": "Search store policies, FAQs, and info (returns, shipping, sizing, payment, warranty, privacy)",
                "args": {"query": "str (required) — the question or topic"},
                "use_when": "User asks about store policy, return policy, shipping, size guide, payment, warranty, or any FAQ-type question",
            },
        ]

        for td in tool_defs:
            td.update(_TOOL_METADATA.get(td["name"], {}))
            self._tools[td["name"]] = td["fn"]
            self._metadata[td["name"]] = {
                "parallel_safe": bool(td.get("parallel_safe", False)),
                "component": td.get("component"),
                "writes": td.get("writes"),
                "depends_on_previous": bool(td.get("depends_on_previous", False)),
                "planner_visible": bool(td.get("planner_visible", True)),
            }
            self._descriptions.append(td)

        logger.info("Registered %d tools", len(self._tools))

    def get_tool(self, name: str) -> Callable:
        tool_fn = self._tools.get(name)
        if not tool_fn:
            raise ValueError(
                f"Tool '{name}' not found. Available: {sorted(self._tools.keys())}"
            )
        return tool_fn

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def get_metadata(self, name: str) -> dict[str, Any]:
        return dict(self._metadata.get(name, {}))

    def is_parallel_safe(self, name: str) -> bool:
        metadata = self._metadata.get(name, {})
        return bool(metadata.get("parallel_safe")) and not metadata.get(
            "depends_on_previous"
        )

    def get_component(self, name: str) -> str | None:
        metadata = self._metadata.get(name, {})
        component = metadata.get("component")
        return component if isinstance(component, str) else None

    def get_product_catalog_text(self) -> str:
        return self._product_catalog

    def get_catalog_product_ids(self) -> list[int]:
        if not self._product_catalog:
            return []
        ids = [int(x) for x in re.findall(r"\bid\s*=\s*(\d+)\b", self._product_catalog)]
        return list(dict.fromkeys(ids))

    def get_valid_product_ids(self, limit: int | None = None) -> list[int]:
        ids = self.get_catalog_product_ids()
        if not ids:
            from api import db as database

            ids = [int(p.get("id")) for p in database.get_all_products() if p.get("id")]
        if limit is not None and limit > 0:
            return ids[:limit]
        return ids

    def get_planner_prompt_text(self) -> str:
        """Build the text that goes into the planner system prompt."""
        lines = []
        for td in self._descriptions:
            if not self._metadata.get(td["name"], {}).get("planner_visible", True):
                continue
            # Show only user-facing args (skip auto-injected ones)
            user_args = {
                k: v for k, v in td["args"].items() if "auto-injected" not in v
            }
            args_str = ", ".join(f"{k}: {v}" for k, v in user_args.items())
            lines.append(
                f"- {td['name']}({args_str}): {td['description']}. "
                f"Use when: {td['use_when']}"
            )
        return "\n".join(lines)


_REGISTRY: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
    return _REGISTRY
