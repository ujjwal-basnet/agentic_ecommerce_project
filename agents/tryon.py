"""TryOnAgent — wraps specialist_agents/tryon.py for the chat pipeline.

When a user types "try on the red shirt" in chat (any channel), this agent:
1. Finds the product by name
2. Reads the user's uploaded photo (from user_image_path)
3. Calls the specialist try-on engine
4. Returns the result image path so the renderer can emit it inline in chat
"""

import logging
from pathlib import Path

from agent_protocol import create_mcp_message
import database
from channels.capabilities import (
    ChannelCapabilities,
    ChannelFeatures,
    WEB_APP,
    truncate_text,
    should_send_component,
)

_log = logging.getLogger(__name__)


class TryOnAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, channel_caps: ChannelCapabilities = None, **kw) -> dict:
        if channel_caps is None:
            channel_caps = WEB_APP
        self._last_tool = "virtual_try_on"
        content = msg.get("content", {})
        product_name = content.get("product_name", "")
        user_image_path = content.get("user_image_path")

        # Need a user photo
        if not user_image_path or not Path(user_image_path).exists():
            if ChannelFeatures.VOICE_OUTPUT in channel_caps.features:
                text = "I'd love to help you try that on, but I need your photo first. Virtual try-on is available on the SmartShop web app."
                return create_mcp_message("TryOnAgent", {
                    "status": "ok", "tool": self._last_tool, "component": None,
                    "text": truncate_text(text, channel_caps),
                    "ssml": f"<speak>{text}</speak>",
                })
            return create_mcp_message("TryOnAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "component": None,
                "text": (
                    "I'd love to help you try that on! "
                    "Please upload your photo first using the photo upload button, "
                    "then ask me to try on the product."
                ),
            })

        # Find the product
        product = None
        if product_name:
            product = database.get_product_by_name(product_name)

        if not product:
            # Try searching
            products = database.search_products(product_name or "wearable", limit=5)
            wearable = [p for p in products if p.get("is_wearable")]
            if wearable:
                product = wearable[0]
            elif products:
                product = products[0]

        if not product:
            return create_mcp_message("TryOnAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "component": None,
                "text": (
                    f"I couldn't find a product called '{product_name}'. "
                    "Could you tell me which product you'd like to try on?"
                ),
            })

        if not product.get("is_wearable"):
            return create_mcp_message("TryOnAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "component": None,
                "text": f"Sorry, '{product['name']}' isn't a wearable item so virtual try-on isn't available for it.",
            })

        # Run the specialist try-on engine
        try:
            from specialist_agents.tryon import try_on

            user_bytes = Path(user_image_path).read_bytes()
            result = try_on(
                product_id=product["id"],
                user_image_bytes=user_bytes,
                filename=Path(user_image_path).name,
            )

            if result.get("success"):
                image_path = result["image_path"]
                text = f"Here's how {product['name']} looks on you!"

                base = {
                    "status": "ok",
                    "tool": self._last_tool,
                    "image_path": image_path,
                    "product_name": product["name"],
                }

                # VOICE: can't show images
                if ChannelFeatures.VOICE_OUTPUT in channel_caps.features:
                    base["text"] = truncate_text(
                        f"Your try-on for {product['name']} is ready! Check the SmartShop app to see the result.",
                        channel_caps,
                    )
                    base["ssml"] = f"<speak>Your try on for {product['name']} is ready! Check the SmartShop app to see the result.</speak>"
                    base["component"] = None
                # WEB: show image inline
                elif should_send_component(channel_caps):
                    base["text"] = text
                    base["component"] = None  # image shown via image_path
                # WHATSAPP/FB/MCP: text + image_path for adapter to handle
                else:
                    base["text"] = truncate_text(text, channel_caps)
                    base["component"] = None

                return create_mcp_message("TryOnAgent", base)
            else:
                return create_mcp_message("TryOnAgent", {
                    "status": "error",
                    "tool": self._last_tool,
                    "component": None,
                    "text": f"Try-on failed: {result.get('error', 'Unknown error')}",
                })

        except Exception as e:
            _log.exception("TryOnAgent generation failed")
            return create_mcp_message("TryOnAgent", {
                "status": "error",
                "tool": self._last_tool,
                "component": None,
                "text": f"Virtual try-on encountered an error: {e}",
            })
