"""TryOnAgent — virtual try-on using OpenAI vision + image generation.

Flow:
1. Extract product name from user query (e.g. "try on Red T-Shirt").
2. Look up the product's image in the database.
3. Find the user's uploaded photo — if missing, ask user to upload.
4. Send both images to OpenAI GPT-4o vision to describe the try-on.
5. Use DALL-E 3 to generate the virtual try-on image.
6. Return the generated image.
"""

import logging
import re
import uuid
from pathlib import Path
from smartshop_mcp import create_mcp_message
import database
import config

_log = logging.getLogger(__name__)

_VISION_SYSTEM = """You are a fashion stylist AI. You will receive two images:
1. A photo of a person (the customer)
2. A photo of a clothing product

Your job is to create a VERY detailed prompt for an image generation AI (DALL-E 3) 
that will produce a realistic photo of THIS EXACT person wearing THIS EXACT product.

Describe in detail:
- The person's appearance: gender, body type, skin tone, hair style/color, facial features
- The product: exact type of clothing, color, pattern, style, fit
- The pose: the person should be standing naturally, facing the camera
- The setting: a clean, neutral studio background with soft lighting
- The overall look: how the product fits on this person naturally

Keep the prompt under 800 characters. Be specific and vivid. 
Output ONLY the image generation prompt, nothing else."""

_VISION_USER = "Image 1 is the customer's photo. Image 2 is the product ({product_name}) they want to try on. Generate a detailed DALL-E prompt showing this person wearing this product."


class TryOnAgent:
    def __init__(self):
        self._last_tool = "virtual_try_on"

    # ── public entry point ──────────────────────────────────────────────
    def handle(self, msg: dict, **kw) -> dict:
        content = msg.get("content", {})
        session_id = content.get("session_id", "")
        user_image_path = content.get("user_image_path") or ""
        query = content.get("query", "") or content.get("product_name", "")

        # 1. Extract product name
        product_name = self._extract_product_name(query)

        # 2. Find product in DB
        product = self._find_product(product_name) if product_name else None
        if not product:
            return self._err(
                f"Could not find product '{product_name or query}'. Please specify a valid product name."
            )

        # 3. Get product image
        product_image_path = product.get("image_path", "")
        if not product_image_path or not Path(product_image_path).exists():
            return self._err(f"No image available for {product['name']}.")

        # 4. Get user photo — prompt to upload if missing
        if not user_image_path:
            user_image_path = self._find_user_image(session_id)

        if not user_image_path or not Path(user_image_path).exists():
            return self._err(
                "Please upload your photo first using the 📎 icon at the bottom-left of the chat, then say 'try on' again!"
            )

        # 5. Generate try-on via OpenAI
        try:
            result_path = self._generate_tryon_openai(
                product_image_path, user_image_path, product["name"]
            )
            return create_mcp_message("TryOnAgent", {
                "status": "ok",
                "tool": self._last_tool,
                "data": {
                    "success": True,
                    "image_path": result_path,
                    "product_name": product["name"],
                },
                "component": "TryOnResult",
                "text": f"Here's how {product['name']} looks on you!",
            })
        except Exception as e:
            _log.exception("TryOn generation failed")
            return self._err(f"Try-on generation failed: {e}")

    # ── OpenAI-powered try-on ───────────────────────────────────────────
    def _generate_tryon_openai(
        self, product_image_path: str, user_image_path: str, product_name: str
    ) -> str:
        from llm import call_llm_vision, generate_image

        # Step 1: Describe the try-on via GPT-4o vision
        _log.info("TryOn Step 1: Sending images to GPT-4o vision…")
        description = call_llm_vision(
            system_prompt=_VISION_SYSTEM,
            text_prompt=_VISION_USER.format(product_name=product_name),
            image_paths=[user_image_path, product_image_path],
            model="gpt-4o",
        )
        _log.info("TryOn vision description: %s", description[:200])

        # Step 2: Generate the try-on image via DALL-E 3
        _log.info("TryOn Step 2: Generating image with DALL-E 3…")
        image_bytes = generate_image(
            prompt=description,
            model="dall-e-3",
            size="1024x1024",
        )

        # Step 3: Save the result
        output_dir = Path(config.TRYON_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"tryon_{uuid.uuid4().hex[:8]}.png"
        out_path = output_dir / out_name
        out_path.write_bytes(image_bytes)
        _log.info("TryOn saved to %s (%d bytes)", out_path, len(image_bytes))
        return str(out_path)

    # ── helpers ─────────────────────────────────────────────────────────
    def _err(self, message: str) -> dict:
        return create_mcp_message("TryOnAgent", {
            "status": "error",
            "tool": self._last_tool,
            "data": {"success": False, "error": message},
            "component": "TryOnResult",
            "text": message,
        })

    def _extract_product_name(self, query: str) -> str:
        if not query:
            return ""
        cleaned = re.sub(
            r"(?i)^(try\s+on\s+|virtual\s+try[-\s]*on\s+|fit\s+on\s+|wear\s+)",
            "", query,
        ).strip()
        return cleaned

    def _find_product(self, name: str) -> dict | None:
        products = database.get_all_products()
        name_lower = name.lower().strip()

        for p in products:
            if p["name"].lower() == name_lower:
                return p
        for p in products:
            pname = p["name"].lower()
            if name_lower in pname or pname in name_lower:
                return p
        tokens = name_lower.split()
        for p in products:
            if all(t in p["name"].lower() for t in tokens):
                return p
        for p in products:
            if all(t in name_lower for t in p["name"].lower().split()):
                return p
        return None

    def _find_user_image(self, session_id: str) -> str:
        user_dir = Path(config.USER_IMAGES_DIR)
        if not user_dir.exists():
            return ""
        candidates = sorted(
            user_dir.glob(f"{session_id}*"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if candidates:
            return str(candidates[0])
        all_images = sorted(
            user_dir.glob("*"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        for img in all_images:
            if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                return str(img)
        return ""
