"""Virtual try-on tools."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from langchain_core.tools import tool

from api import config
from api import db as database

logger = logging.getLogger(__name__)

_TRYON_PROMPT = """You are an AI-powered virtual try-on engine.

INPUTS:
- Person: the user image
- Item: the product image

STEP 1 — DETECT ITEM:
Look at the product image and identify:
- Item type (clothing / eyewear / footwear / accessory / bag / jewelry)
- Color, texture, pattern, material
- Style (casual, formal, sporty, luxury)

STEP 2 — ANALYZE PERSON:
From the user image extract:
- Body pose and angle
- Skin tone and lighting direction
- Current outfit (to understand layering context)
- Background

STEP 3 — PLACE ITEM:
- Map item to correct body region automatically
- Adjust scale, perspective, drape, and fit to body
- Simulate fabric physics if clothing (wrinkles, folds, gravity)
- Simulate reflection/refraction if glasses or jewelry
- Simulate sole angle if footwear

STEP 4 — BLEND:
- Match shadows and highlights of item to scene lighting
- Ensure edges look natural, no hard cutouts
- Maintain photorealism throughout

STEP 5 — OUTPUT:
- Single merged image
- Same resolution and aspect ratio as the user image
- Person looks like they are actually wearing the item
- No other changes to the image

QUALITY RULES:
- Never distort the person's face
- Never change background
- Never add items not in the product image
- If item cannot be placed realistically, say why"""


@tool
def perform_virtual_try_on(product_id: int, user_image_path: str) -> str:
    """Virtual try-on via Gemini image model. Only runs for products the owner flagged as wearable."""
    try:
        if not user_image_path or not Path(user_image_path).exists():
            return json.dumps(
                {
                    "success": False,
                    "error": "User photo not found. Please upload a photo first.",
                }
            )

        product = database.get_product_by_id(product_id)
        if not product:
            return json.dumps(
                {"success": False, "error": f"Product #{product_id} not found"}
            )

        if not product.get("is_wearable"):
            return json.dumps(
                {
                    "success": False,
                    "error": f"'{product['name']}' is not marked as wearable. Only owner-flagged wearables can be tried on.",
                }
            )

        product_image_path = product.get("image_path", "")
        if not product_image_path or not Path(product_image_path).exists():
            return json.dumps(
                {"success": False, "error": f"No image for '{product['name']}'"}
            )

        from google import genai
        from google.oauth2 import service_account
        from PIL import Image

        try:
            client = genai.Client(api_key=config.GOOGLE_API_KEY)

        except Exception as e:
            logger.exception("Try-on: Google credentials failed")
            return json.dumps({"success": False, "error": f"Credentials failed: {e}"})

        user_img = Image.open(user_image_path)
        product_img = Image.open(product_image_path)

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[_TRYON_PROMPT, user_img, product_img],
        )

        from api.integrations import storage as _storage

        output_dir = Path(config.TRYON_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = f"tryon_{uuid.uuid4().hex[:8]}.png"

        for cand in response.candidates or []:
            parts = getattr(cand.content, "parts", []) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    url = _storage.upload("tryon-results", fname, inline.data)
                    if url:
                        img_result = url
                    else:
                        out_path = output_dir / fname
                        out_path.write_bytes(inline.data)
                        img_result = str(out_path)
                    return json.dumps(
                        {
                            "success": True,
                            "image_path": img_result,
                            "message": f"Try-on generated for {product['name']}",
                            "model": config.GEMINI_IMAGE_MODEL,
                        }
                    )

        return json.dumps(
            {
                "success": False,
                "error": "Image model returned no image data. Try a different photo.",
            }
        )
    except Exception as e:
        logger.exception("perform_virtual_try_on failed")
        return json.dumps({"success": False, "error": f"Try-on failed: {e}"})
