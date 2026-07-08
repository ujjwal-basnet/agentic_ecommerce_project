"""TryOnAgent using FLUX.1 Kontext for virtual try-on."""

from __future__ import annotations

import asyncio
import logging

from api.db.products import get_product_by_id
from api.image_backends import generate_image

logger = logging.getLogger(__name__)


async def tryon_impl(params: dict) -> dict:
    """Perform virtual try-on using the selected image generation model.

    Params:
        product_id (int): ID of the product to try on.
        user_image_path (str): Path to the user's photo.
        model (str): Image model to use (flux_kontext, flux_kontext_720, gptimage, gemini).

    Returns:
        dict with keys: image_path (str), success (bool), product_name (str).
    """
    product_id = params.get("product_id")
    user_image_path = params.get("user_image_path", "")
    model = params.get("model", "nano_banana")

    if not product_id:
        return {
            "success": False,
            "error": "product_id is required for virtual try-on.",
            "image_path": None,
        }

    if not user_image_path:
        return {
            "success": False,
            "error": "user_image_path is required for virtual try-on.",
            "image_path": None,
        }

    product = await asyncio.to_thread(get_product_by_id, int(product_id))
    if not product:
        return {
            "success": False,
            "error": f"Product with ID {product_id} not found.",
            "image_path": None,
        }

    product_name = product.get("name", "")
    product_color = product.get("color", "")
    product_category = product.get("category", "")

    # FLUX Kontext works best with explicit edit instructions
    prompt = (
        f"Keep the exact same person, same pose, same face, same background. "
        f"Change their clothing to: {product_name}. "
        f"The garment is {product_color} colored, category: {product_category}. "
        f"Make the clothing fit naturally on the person's body. "
        f"Photorealistic result, natural lighting, no artifacts."
    )

    try:
        image_path = await generate_image(
            prompt=prompt,
            reference_image_path=user_image_path,
            model=model,
            is_tryon=True,
        )
        return {
            "success": True,
            "image_path": image_path,
            "product_name": product_name,
        }
    except Exception as e:
        logger.error("Try-on image generation failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "image_path": None,
        }
