"""OwnerAgent — analytics, inventory, facebook. Sets _last_tool per action."""

import requests
from pathlib import Path
from mcp import create_mcp_message
import database
import config


class OwnerAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, **kw) -> dict:
        content = msg.get("content", {})
        action = content.get("action", "analytics")
        params = content.get("params", {})

        try:
            if action == "analytics":
                return self._analytics(params)
            elif action == "inventory":
                return self._inventory(params)
            elif action == "post_facebook":
                return self._post_facebook(params)
            elif action == "add_product":
                return self._add_product(params)
            else:
                return self._analytics(params)
        except Exception as e:
            return create_mcp_message("OwnerAgent", {
                "status": "error",
                "tool": self._last_tool or "get_analytics",
                "error": str(e),
                "text": f"Owner action '{action}' failed.",
                "component": None,
            })

    def _analytics(self, params: dict) -> dict:
        self._last_tool = "get_analytics"
        days = params.get("days", 30)
        stats = database.get_summary_stats()
        revenue = database.get_revenue_by_day(days)
        top = database.get_top_products(5)
        by_cat = database.get_revenue_by_category()
        stock = database.get_stock_levels()
        orders = database.get_recent_orders(10)

        data = {
            "stats": stats,
            "revenue": revenue,
            "top": top,
            "by_cat": by_cat,
            "stock": stock,
            "orders": orders,
        }
        return create_mcp_message("OwnerAgent", {
            "status": "ok",
            "tool": self._last_tool,
            "data": data,
            "component": None,
            "text": (
                f"Dashboard: {stats['total_orders']} orders, "
                f"Rs. {stats['total_revenue']} revenue, "
                f"{stats['total_products']} products."
            ),
        })

    def _inventory(self, params: dict) -> dict:
        self._last_tool = "get_inventory"
        products = database.get_all_products()
        low_stock = [p for p in products if int(p.get("quantity", 0)) < 5]
        return create_mcp_message("OwnerAgent", {
            "status": "ok",
            "tool": self._last_tool,
            "data": {"products": products, "low_stock": low_stock},
            "component": None,
            "text": f"{len(products)} products in inventory. {len(low_stock)} low stock.",
        })

    def _post_facebook(self, params: dict) -> dict:
        self._last_tool = "post_to_facebook"
        image_path = params.get("image_path", "")
        caption = params.get("caption", "")

        if not config.facebook_enabled():
            return create_mcp_message("OwnerAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": "Facebook not configured.",
                "text": "Facebook API credentials not set.",
                "component": None,
            })

        if not Path(image_path).exists():
            return create_mcp_message("OwnerAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": f"Image not found: {image_path}",
                "text": "Image file not found.",
                "component": None,
            })

        url = (
            f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}/"
            f"{config.FB_PAGE_ID}/photos"
        )
        with open(image_path, "rb") as f:
            resp = requests.post(url, files={"source": f}, data={
                "caption": caption, "published": "true",
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
            }, timeout=60)

        if resp.status_code == 200:
            return create_mcp_message("OwnerAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "data": {"post_id": resp.json().get("id")},
                "component": None,
                "text": "Posted to Facebook!",
            })

        return create_mcp_message("OwnerAgent", {
            "status": "error",
            "tool": self._last_tool,
            "error": resp.text,
            "text": "Facebook post failed.",
            "component": None,
        })

    def _add_product(self, params: dict) -> dict:
        self._last_tool = "add_product"
        pid = database.insert_product(
            name=params.get("name", ""),
            category=params.get("category", ""),
            color=params.get("color", ""),
            price=float(params.get("price", 0)),
            description=params.get("description", ""),
            quantity=int(params.get("quantity", 0)),
            image_path=params.get("image_path", ""),
            tags=params.get("tags", "[]"),
            is_wearable=int(params.get("is_wearable", 0)),
        )
        return create_mcp_message("OwnerAgent", {
            "status": "ok",
            "tool": self._last_tool,
            "data": {"product_id": pid},
            "component": None,
            "text": f"Product added (id={pid}).",
        })
