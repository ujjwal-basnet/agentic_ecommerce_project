"""RecommendAgent — product recommendations. Sets _last_tool = 'recommend'."""

from mcp import create_mcp_message

class RecommendAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, **kw) -> dict:
        self._last_tool = "recommend"

        try:
            products = database.get_all_products()
            if not products:
                return create_mcp_message("RecommendAgent", {
                    "status": "ok",
                    "tool": self._last_tool,
                    "products": [],
                    "component": "RecommendGrid",
                    "text": "No products available for recommendations right now.",
                })

            in_stock = [p for p in products if int(p.get("quantity", 0)) > 0]
            if not in_stock:
                in_stock = products

            by_qty = sorted(in_stock, key=lambda x: int(x.get("quantity", 0)), reverse=True)
            by_price = sorted(in_stock, key=lambda x: float(x.get("price", 0)))

            recs = []
            seen = set()
            for src in [by_qty, by_price]:
                for p in src:
                    pid = p.get("id")
                    if pid not in seen and len(recs) < 8:
                        seen.add(pid)
                        recs.append({
                            "id": p.get("id"),
                            "name": p.get("name", ""),
                            "category": p.get("category", ""),
                            "color": p.get("color", ""),
                            "price": float(p.get("price", 0)),
                            "description": p.get("description", ""),
                            "image_path": p.get("image_path", ""),
                            "quantity": int(p.get("quantity", 0)),
                            "is_wearable": bool(p.get("is_wearable", 0)),
                        })

            return create_mcp_message("RecommendAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "products": recs,
                "component": "RecommendGrid",
                "text": f"Here are {len(recs)} recommendations for you!",
            })

        except Exception as e:
            return create_mcp_message("RecommendAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": "Could not fetch recommendations.",
                "products": [],
                "component": None,
            })
