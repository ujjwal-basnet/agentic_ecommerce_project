"""TryOn Specialist Agent — virtual try-on using image editing.

Uses OpenAI's image edit endpoint (gpt-image-1) so the user's actual
photo is preserved — same face, same pose, same background — only
the clothing is swapped.
"""

import logging
import uuid
from pathlib import Path

import config
import database

_log = logging.getLogger(__name__)

# ── Prompts ────────────────────────────────────────────────────────────────

_PRODUCT_DESCRIBE_SYSTEM = """You are a fashion expert. You will receive an image of a clothing product.
Describe it in precise detail: garment type, color, pattern, fabric texture, fit, neckline, sleeve style,
hem length, any logos or details. Be concise and factual. Output ONLY the description, nothing else."""

_EDIT_PROMPT_TEMPLATE = (
    "Dress the person in this photo with the following clothing item: {product_description}. "
    "IMPORTANT RULES — strictly follow all of them:\n"
    "- Do NOT change the person's face, skin tone, hair, or body shape in any way.\n"
    "- Do NOT change the person's pose or position.\n"
    "- Do NOT change the background or lighting.\n"
    "- Only replace the clothing with the described item.\n"
    "- The result must look like a real, natural photo — not a cartoon or illustration.\n"
    "- The clothing must fit naturally on the person's body."
)


# ── Public API ─────────────────────────────────────────────────────────────

def try_on(product_id: int, user_image_bytes: bytes, filename: str = "photo.jpg") -> dict:
    """Run virtual try-on for a product.

    Args:
        product_id: DB product ID
        user_image_bytes: raw bytes of the user's uploaded photo
        filename: original filename (for extension detection)

    Returns:
        dict with keys: success, image_path (relative), error
    """
    # 1. Look up product
    product = database.get_product_by_id(product_id)
    if not product:
        return {"success": False, "error": f"Product #{product_id} not found."}

    product_image_path = product.get("image_path", "")
    if not product_image_path or not Path(product_image_path).exists():
        return {"success": False, "error": f"No image available for '{product['name']}'."}

    # 2. Save user photo
    ext = Path(filename).suffix or ".jpg"
    user_dir = Path(config.USER_IMAGES_DIR)
    user_dir.mkdir(parents=True, exist_ok=True)
    user_path = user_dir / f"tryon_user_{uuid.uuid4().hex[:8]}{ext}"
    user_path.write_bytes(user_image_bytes)

    # 3. Edit user photo to wear the product
    try:
        result_path = _generate(product_image_path, str(user_path), product["name"])
        return {
            "success": True,
            "image_path": result_path,
            "product_name": product["name"],
        }
    except Exception as e:
        _log.exception("TryOn generation failed")
        return {"success": False, "error": str(e)}


# ── Core logic ─────────────────────────────────────────────────────────────

def _generate(product_image_path: str, user_image_path: str, product_name: str) -> str:
    from llm import call_llm_vision
    import openai

    client = openai.OpenAI()

    # Step 1: Describe the product precisely using vision
    _log.info("TryOn Step 1: Describing product '%s'", product_name)
    product_description = call_llm_vision(
        system_prompt=_PRODUCT_DESCRIBE_SYSTEM,
        text_prompt=f"Describe this clothing product called '{product_name}' in detail.",
        image_paths=[product_image_path],
        model="gpt-4o",
    )
    _log.info("Product description: %s", product_description[:200])

    # Step 2: Edit the user's photo — apply clothing, preserve everything else
    edit_prompt = _EDIT_PROMPT_TEMPLATE.format(product_description=product_description)
    _log.info("TryOn Step 2: Editing user photo with gpt-image-1")

    with open(user_image_path, "rb") as user_img:
        response = client.images.edit(
            model="gpt-image-1",
            image=user_img,
            prompt=edit_prompt,
            size="1024x1024",
        )

    # Step 3: Decode and save result
    import base64
    image_data = response.data[0].b64_json
    image_bytes = base64.b64decode(image_data)

    output_dir = Path(config.TRYON_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"tryon_{uuid.uuid4().hex[:8]}.png"
    out_path = output_dir / out_name
    out_path.write_bytes(image_bytes)

    _log.info("TryOn saved: %s (%d bytes)", out_path, len(image_bytes))
    return str(out_path)