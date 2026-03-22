"""CartAgent — add/view/remove/clear/update. Sets _last_tool per action."""

from mcp import create_mcp_message
import database


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

    def handle(self, msg: dict, **kw) -> dict:
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
                return create_mcp_message("CartAgent", {
                    "status": "ok",
                    "tool": self._last_tool,
                    "success": True,
                    "message": f"Added {quantity}x {product_name} to cart!",
                    "items": cart,
                    "count": count,
                    "total": total,
                    "component": "CartConfirmation",
                    "text": f"Added {quantity}x {product_name} to cart!",
                })

            elif action == "remove" and product_name:
                database.db_remove_from_cart(session_id, product_name)
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                return create_mcp_message("CartAgent", {
                    "status": "ok",
                    "tool": "remove_from_cart",
                    "success": True,
                    "message": f"Removed {product_name} from cart.",
                    "items": cart,
                    "count": count,
                    "total": total,
                    "component": "CartConfirmation",
                    "text": f"Removed {product_name} from cart.",
                })

            elif action == "clear":
                database.db_clear_cart(session_id)
                return create_mcp_message("CartAgent", {
                    "status": "ok",
                    "tool": "clear_cart",
                    "success": True,
                    "message": "Cart cleared!",
                    "items": [],
                    "count": 0,
                    "total": 0.0,
                    "component": "CartDrawer",
                    "text": "Cart cleared!",
                })

            elif action == "update" and product_name:
                database.db_update_cart_quantity(session_id, product_name, int(quantity or 1))
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                return create_mcp_message("CartAgent", {
                    "status": "ok",
                    "tool": "update_cart",
                    "success": True,
                    "message": f"Updated {product_name} quantity to {quantity}.",
                    "items": cart,
                    "count": count,
                    "total": total,
                    "component": "CartDrawer",
                    "text": f"Updated {product_name} quantity to {quantity}.",
                })

            else:  # view
                cart = database.db_get_cart(session_id)
                count = sum(int(i.get("quantity", 0)) for i in cart)
                total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
                if not cart:
                    return create_mcp_message("CartAgent", {
                        "status": "ok",
                        "tool": "view_cart",
                        "items": [],
                        "count": 0,
                        "total": 0.0,
                        "component": "CartDrawer",
                        "text": "Your cart is empty. Start shopping!",
                    })
                return create_mcp_message("CartAgent", {
                    "status": "ok",
                    "tool": "view_cart",
                    "items": cart,
                    "count": count,
                    "total": total,
                    "component": "CartDrawer",
                    "text": f"You have {count} item{'s' if count != 1 else ''} in your cart (Rs. {total}).",
                })

        except Exception as e:
            return create_mcp_message("CartAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": "Cart operation failed.",
                "component": None,
            })
