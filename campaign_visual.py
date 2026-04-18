"""Campaign visual generator — composes product + model photo + prompt via Gemini image model."""

from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

from google import genai
from google.oauth2 import service_account
from PIL import Image

import config

log = logging.getLogger("smartshop.campaign_visual")

CAMPAIGN_DIR = Path(config.CAMPAIGN_DIR)
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client

    if config.GOOGLE_GENAI_USE_VERTEXAI:
        creds = service_account.Credentials.from_service_account_file(
            str(Path(config.GOOGLE_APPLICATION_CREDENTIALS).expanduser()),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        _client = genai.Client(
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION,
            credentials=creds,
        )
    else:
        _client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _client


def _load_image(path: str | None) -> Image.Image | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        log.warning("campaign_visual: image not found at %s", p)
        return None
    return Image.open(p)


def generate_campaign_image(
    product_image_path: str,
    model_image_path: str | None,
    prompt: str,
    background_image_path: str | None = None,
) -> str:
    """Generate one campaign image from product + optional model photo + optional background + prompt.

    Returns the absolute path of the saved PNG.
    """
    product_img = _load_image(product_image_path)
    if product_img is None:
        raise FileNotFoundError(f"Product image not found: {product_image_path}")
    model_img = _load_image(model_image_path)
    background_img = _load_image(background_image_path)

    direction = (prompt or "Editorial lifestyle product shot, studio lighting, minimalist background.").strip()
    if model_img is not None:
        framing = (
            "Compose a high-end marketing photograph featuring the person in the MODEL reference "
            "wearing, holding, or using the PRODUCT shown in the product reference. Keep the "
            "person's face, skin tone, and proportions realistic and consistent with the reference. "
        )
    else:
        framing = (
            "Compose a high-end marketing photograph of the PRODUCT shown in the reference, "
            "framed as an editorial hero shot. "
        )
    if background_img is not None:
        framing += (
            "Use the BACKGROUND reference image as the environment/backdrop for the scene — match "
            "its colors, lighting mood, and overall atmosphere. "
        )
    full_prompt = (
        framing
        + f"Direction: {direction} "
        + "Output a single photorealistic image, no text overlays, no watermarks."
    )

    contents: list = [full_prompt, product_img]
    if model_img is not None:
        contents.append(model_img)
    if background_img is not None:
        contents.append(background_img)

    client = _get_client()
    response = client.models.generate_content(
        model=config.GEMINI_IMAGE_MODEL,
        contents=contents,
    )

    out_path = CAMPAIGN_DIR / f"campaign_{uuid.uuid4().hex[:10]}.png"

    for cand in response.candidates or []:
        parts = getattr(cand.content, "parts", []) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                out_path.write_bytes(inline.data)
                log.info("campaign_visual: wrote %s", out_path)
                return str(out_path)

    raise RuntimeError("Gemini image model returned no image data")
