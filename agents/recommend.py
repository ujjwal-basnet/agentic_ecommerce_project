"""RecommendAgent — product recommendations. Sets _last_tool = 'recommend'."""

from agent_protocol import create_mcp_message
import database
from channels.capabilities import (
    ChannelCapabilities,
    ChannelFeatures,
    WEB_APP,
    WHATSAPP,
    FB_MESSENGER,
    truncate_text,
    should_send_component,
)


class RecommendAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, channel_caps: ChannelCapabilities = None, **kw) -> dict:
        if channel_caps is None:
            channel_caps = WEB_APP

        self._last_tool = "recommend"

        try:
            products = database.get_all_products()
            if not products:
                return create_mcp_message("RecommendAgent", {
                    "status": "ok",
                    "tool": self._last_tool,
                    "products": [],
                    "component": None,
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

            return self._format_for_channel(recs, channel_caps)

        except Exception as e:
            return create_mcp_message("RecommendAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": "Could not fetch recommendations.",
                "products": [],
                "component": None,
            })

    def _format_for_channel(self, recs: list[dict], caps: ChannelCapabilities) -> dict:
        """Format recommendations based on channel capabilities."""
        base = {
            "status": "ok",
            "tool": self._last_tool,
            "products": recs,
        }

        # VOICE: short speakable summary + SSML
        if ChannelFeatures.VOICE_OUTPUT in caps.features:
            names = [r["name"] for r in recs[:3]]
            text = f"I recommend {', '.join(names)}." if names else "No recommendations right now."
            if len(recs) > 3:
                text += f" Plus {len(recs) - 3} more. Say an item name to hear details."
            base["text"] = truncate_text(text, caps)
            base["ssml"] = f"<speak>{text}</speak>"
            base["component"] = None
            return create_mcp_message("RecommendAgent", base)

        # WHATSAPP: numbered list, no markdown
        if caps == WHATSAPP:
            lines = [f"{len(recs)} recommendations for you:\n"]
            for i, r in enumerate(recs[:caps.max_carousel_items], 1):
                lines.append(f"{i}. {r['name']} - Rs.{r['price']}")
            base["text"] = truncate_text("\n".join(lines), caps)
            base["quick_replies"] = [
                {"title": f"Buy #{i}", "payload": f"buy_{r['id']}"}
                for i, r in enumerate(recs[:3], 1)
            ]
            base["component"] = None
            return create_mcp_message("RecommendAgent", base)

        # FB MESSENGER: generic template carousel with images
        if caps == FB_MESSENGER:
            base["text"] = f"Here are {len(recs)} recommendations!"
            base["fb_template"] = {
                "type": "generic",
                "elements": [
                    {
                        "title": r["name"][:80],
                        "subtitle": f"Rs.{r['price']} | {r['category']}"[:80],
                        "image_url": r.get("image_path", ""),
                        "buttons": [
                            {"type": "postback", "title": "Add to Cart", "payload": f"add_{r['id']}"},
                            {"type": "postback", "title": "Details", "payload": f"detail_{r['id']}"},
                        ][:caps.max_buttons],
                    }
                    for r in recs[:caps.max_carousel_items]
                ],
            }
            base["component"] = None
            return create_mcp_message("RecommendAgent", base)

        # WEB: React component
        if should_send_component(caps):
            base["text"] = f"Here are {len(recs)} recommendations for you!"
            base["component"] = "RecommendGrid"
            return create_mcp_message("RecommendAgent", base)

        # MCP / plain text fallback
        lines = [f"Here are {len(recs)} recommendations:\n"]
        for r in recs:
            stock = "In stock" if r.get("quantity", 0) > 0 else "Out of stock"
            lines.append(f"• {r['name']} — Rs.{r['price']} ({r['category']}) — {stock}")
        base["text"] = truncate_text("\n".join(lines), caps)
        base["component"] = None
        return create_mcp_message("RecommendAgent", base)
