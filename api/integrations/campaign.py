"""Campaign visual generator — multi-backend (Runflow, RunPod, Gemini, OpenAI)."""

from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

import requests
from PIL import Image

from api import config
from api.image_backends import generate_image as backend_generate, _upload_to_temp_url, _resolve_image_path

log = logging.getLogger("smartshop.campaign_visual")

CAMPAIGN_DIR = Path(config.CAMPAIGN_DIR)
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)


def _load_image(path: str | None) -> Image.Image | None:
    """Load an image from a local path OR an http(s) URL."""
    if not path:
        return None

    if str(path).startswith(("http://", "https://")):
        try:
            resp = requests.get(path, timeout=15)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content))
        except Exception as exc:
            log.warning("campaign_visual: failed to fetch %s: %s", path, exc)
            return None

    p = Path(path)
    if not p.exists():
        log.warning("campaign_visual: image not found at %s", p)
        return None
    return Image.open(p)


def _image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    if img.mode == "RGBA" and fmt == "JPEG":
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    return buf.getvalue()


def _save_reference_image(img: Image.Image) -> str:
    """Save a PIL image to a temp file and return the path."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(_image_to_bytes(img))
        return tmp.name


async def generate_campaign_image_async(
    product_image_path: str,
    model_image_path: str | None,
    prompt: str,
    background_image_path: str | None = None,
    image_model: str = "nano_banana",
) -> str:
    """Generate one campaign image using the selected backend.

    Returns the URL-routable path of the saved image.
    """
    product_img = _load_image(product_image_path)
    if product_img is None:
        raise FileNotFoundError(f"Product image not found: {product_image_path}")

    model_img = _load_image(model_image_path)
    background_img = _load_image(background_image_path)

    # Build the prompt
    direction = (
        prompt
        or "Editorial lifestyle product shot, studio lighting, minimalist background."
    ).strip()

    if model_img is not None:
        framing = (
            "Create a high-end marketing photograph featuring the person "
            "wearing or using the product shown. Keep the person's appearance "
            "realistic and consistent with the reference. "
        )
    else:
        framing = (
            "Create a high-end marketing photograph of the product shown, "
            "framed as an editorial hero shot. "
        )

    if background_img is not None:
        framing += "Use the background reference for the environment/backdrop. "

    full_prompt = (
        framing
        + f"Direction: {direction} "
        + "Output a single photorealistic image, no text overlays, no watermarks."
    )

    # Upload extra images (model photo, background) as public URLs for Runflow
    extra_image_urls: list[str] = []
    if model_img is not None:
        model_bytes = _image_to_bytes(model_img)
        url = await _upload_to_temp_url(model_bytes, "image/png")
        extra_image_urls.append(url)
    if background_img is not None:
        bg_bytes = _image_to_bytes(background_img)
        url = await _upload_to_temp_url(bg_bytes, "image/png")
        extra_image_urls.append(url)

    # Save product image as reference for models that support editing
    ref_path = _save_reference_image(product_img)

    try:
        out_path = await backend_generate(
            prompt=full_prompt,
            reference_image_path=ref_path,
            model=image_model,
            is_tryon=False,
            extra_image_urls=extra_image_urls or None,
        )
    finally:
        Path(ref_path).unlink(missing_ok=True)

    return out_path


def generate_campaign_image(
    product_image_path: str,
    model_image_path: str | None,
    prompt: str,
    background_image_path: str | None = None,
    image_model: str = "nano_banana",
) -> str:
    """Sync wrapper for generate_campaign_image_async."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                generate_campaign_image_async(
                    product_image_path, model_image_path, prompt,
                    background_image_path, image_model,
                ),
            )
            return future.result()
    return asyncio.run(
        generate_campaign_image_async(
            product_image_path, model_image_path, prompt,
            background_image_path, image_model,
        )
    )
