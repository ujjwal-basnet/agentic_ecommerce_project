"""CartAgent — add/view/remove/clear/update. Sets _last_tool per action."""

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


_ACTION_TOOL = {
    "add": "add_to_cart",
    "view": "view_cart",
    "remove": "remove_from_cart",
    "update": "update_cart",
    "clear": "clear_cart",
}


class CartAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, channel_caps: ChannelCapabilities = None, **kw) -> dict:
        if channel_caps is None:
            channel_caps = WEB_APP

        content = msg.get("content", {})
        action = content.get("action", "view")
        session_id = content.get("session_id", "")
        product_name = content.get("product_name")
        price = content.get("price")
        quantity = content.get("quantity", 1)

        self._last_tool = _ACTION_TOOL.get(action, "view_cart")

        try:
            if action == "add" and product_name:
                if price is None:
                    prod = database.get_product_by_name(product_name)
                    if prod:
                        price = prod["price"]
                        product_name = prod["name"]
                    else:
                        return create_mcp_message("CartAgent", {
                            "status": "error",
                            "tool": self._last_tool,
                            "text": f"Product '{product_name}' not found.",
                            "component": None,
                        })
                database.db_add_to_cart(session_id, product_name, float(price), int(quantity or 1))
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                text = f"Added {quantity}x {product_name} to cart!"
                return self._format("ok", self._last_tool, text, cart, count, total, channel_caps)

            elif action == "remove" and product_name:
                database.db_remove_from_cart(session_id, product_name)
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                text = f"Removed {product_name} from cart."
                return self._format("ok", "remove_from_cart", text, cart, count, total, channel_caps)

            elif action == "clear":
                database.db_clear_cart(session_id)
                return self._format("ok", "clear_cart", "Cart cleared!", [], 0, 0.0, channel_caps)

            elif action == "update" and product_name:
                database.db_update_cart_quantity(session_id, product_name, int(quantity or 1))
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                text = f"Updated {product_name} quantity to {quantity}."
                return self._format("ok", "update_cart", text, cart, count, total, channel_caps)

            else:  # view
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                if not cart:
                    return self._format("ok", "view_cart", "Your cart is empty. Start shopping!", [], 0, 0.0, channel_caps)
                text = f"You have {count} item{'s' if count != 1 else ''} in your cart (Rs. {total})."
                return self._format("ok", "view_cart", text, cart, count, total, channel_caps)

        except Exception as e:
            return create_mcp_message("CartAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": "Cart operation failed.",
                "component": None,
            })

    def _format(
        self,
        status: str,
        tool: str,
        text: str,
        cart: list,
        count: int,
        total: float,
        caps: ChannelCapabilities,
    ) -> dict:
        """Format cart response based on channel capabilities."""
        base = {
            "status": status,
            "tool": tool,
            "success": status == "ok",
            "items": cart,
            "count": count,
            "total": total,
            "cart_count": count,
        }

        # VOICE: short speakable text + SSML
        if ChannelFeatures.VOICE_OUTPUT in caps.features:
            if cart:
                summary = f"{count} item{'s' if count != 1 else ''}, total Rs. {total}."
                voice_text = f"{text} {summary}"
                base["ssml"] = (
                    f"<speak>{text} You have <say-as interpret-as='cardinal'>{count}</say-as> "
                    f"items totalling <say-as interpret-as='cardinal'>{int(total)}</say-as> rupees.</speak>"
                )
            else:
                voice_text = text
                base["ssml"] = f"<speak>{text}</speak>"
            base["text"] = truncate_text(voice_text, caps)
            base["component"] = None
            return create_mcp_message("CartAgent", base)

        # WHATSAPP: numbered list, no markdown
        if caps == WHATSAPP:
            if cart:
                lines = [text, ""]
                for i, item in enumerate(cart[:caps.max_carousel_items], 1):
                    lines.append(
                        f"{i}. {item['product_name']} x{item['quantity']} - Rs.{item['price']}"
                    )
                lines.append(f"\nTotal: Rs.{total}")
                base["text"] = truncate_text("\n".join(lines), caps)
                base["quick_replies"] = [
                    {"title": "Checkout", "payload": "checkout"},
                    {"title": "Clear cart", "payload": "clear_cart"},
                ]
            else:
                base["text"] = text
            base["component"] = None
            return create_mcp_message("CartAgent", base)

        # FB MESSENGER: structured template
        if caps == FB_MESSENGER:
            if cart:
                base["text"] = truncate_text(text, caps)
                base["fb_template"] = {
                    "type": "button",
                    "text": f"Cart: {count} items — Rs.{total}",
                    "buttons": [
                        {"type": "postback", "title": "Checkout", "payload": "checkout"},
                        {"type": "postback", "title": "View Cart", "payload": "view_cart"},
                    ][:caps.max_buttons],
                }
            else:
                base["text"] = text
            base["component"] = None
            return create_mcp_message("CartAgent", base)

        # WEB: React component
        if should_send_component(caps):
            base["text"] = text
            base["component"] = "CartDrawer" if tool in ("view_cart", "clear_cart", "update_cart") else "CartConfirmation"
            return create_mcp_message("CartAgent", base)

        # MCP / plain text fallback
        if cart:
            lines = [text, ""]
            for item in cart:
                lines.append(f"• {item['product_name']} x{item['quantity']} — Rs.{item['price']}")
            lines.append(f"\nTotal: {count} item(s), Rs.{total}")
            base["text"] = truncate_text("\n".join(lines), caps)
        else:
            base["text"] = text
        base["component"] = None
        return create_mcp_message("CartAgent", base)
