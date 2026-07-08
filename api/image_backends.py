"""Multi-backend image generation — RunPod FLUX Kontext, Gemini, OpenAI.

Each backend implements `generate(prompt, reference_image_path?) -> file_path`.
The `generate_image` dispatcher selects the backend based on the `model` param.

Cost comparison (at 1024x1024):
  - flux_kontext: $0.025/img (RunPod, best try-on quality)
  - flux_kontext_720: $0.013/img (RunPod, 720p cheaper)
  - gptimage: ~$0.02/img (OpenAI, good quality)
  - gemini: ~$0.014/img (Google, quota-limited)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx

from api import config

logger = logging.getLogger(__name__)

# ── Registry ────────────────────────────────────────────────────────────────

IMAGE_MODELS = {
    "nano_banana": {
        "id": "nano_banana",
        "label": "🆓 Nano Banana 2",
        "description": "FREE · Google · $0.08/img",
        "supports_edit": True,
    },
    "gpt_image_2": {
        "id": "gpt_image_2",
        "label": "🆓 GPT Image 2",
        "description": "FREE · OpenAI · $0.133/img",
        "supports_edit": True,
    },
    "flux_kontext": {
        "id": "flux_kontext",
        "label": "FLUX Kontext 1080p",
        "description": "Best try-on · $0.025/img",
        "supports_edit": True,
    },
    "flux_kontext_720": {
        "id": "flux_kontext_720",
        "label": "FLUX Kontext 720p",
        "description": "Fast try-on · $0.025/img",
        "supports_edit": True,
    },
    "gptimage": {
        "id": "gptimage",
        "label": "GPT Image 1",
        "description": "OpenAI · $0.02/img",
        "supports_edit": True,
    },
    "gemini": {
        "id": "gemini",
        "label": "Gemini Flash",
        "description": "Google · quota-limited",
        "supports_edit": True,
    },
}

DEFAULT_MODEL = "nano_banana"


def _output_dir(is_tryon: bool) -> Path:
    d = Path(config.TRYON_DIR if is_tryon else config.CAMPAIGN_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_image(image_bytes: bytes, is_tryon: bool, ext: str = ".png") -> str:
    prefix = "tryon" if is_tryon else "campaign"
    fname = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
    out = _output_dir(is_tryon) / fname
    out.write_bytes(image_bytes)
    logger.info("image saved: %s (%d bytes)", out, len(image_bytes))
    url_prefix = "data/tryon" if is_tryon else "data/campaigns"
    return f"{url_prefix}/{fname}"


async def _resolve_image_path(path: str) -> tuple[bytes, str]:
    """Resolve a reference image path to (bytes, mime_type)."""
    if path.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(path)
            resp.raise_for_status()
            img_bytes = resp.content
        low = path.lower().split("?")[0]
        if low.endswith((".png",)):
            mime = "image/png"
        else:
            mime = "image/jpeg"
        return img_bytes, mime

    local = Path(path)
    if not local.exists():
        raise FileNotFoundError(f"Reference image not found: {path}")
    img_bytes = local.read_bytes()
    mime = "image/jpeg" if local.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return img_bytes, mime


async def _resolve_to_local_file(path: str) -> str:
    """Ensure the image is available as a local file."""
    if not path.startswith(("http://", "https://")):
        if not Path(path).exists():
            raise FileNotFoundError(f"Reference image not found: {path}")
        return path

    import tempfile
    img_bytes, mime = await _resolve_image_path(path)
    ext = ".png" if "png" in mime else ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(img_bytes)
    tmp.close()
    return tmp.name


def _image_to_data_url(img_bytes: bytes, mime: str) -> str:
    """Convert image bytes to a data URL for APIs that need it."""
    b64 = base64.b64encode(img_bytes).decode()
    return f"data:{mime};base64,{b64}"


async def _upload_to_temp_url(img_bytes: bytes, mime: str) -> str:
    """Upload image to Supabase for public URL access, or fallback to tmpfiles.org."""
    if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
        try:
            ext = "png" if "png" in mime else "jpg"
            fname = f"temp_tryon_{uuid.uuid4().hex[:8]}.{ext}"
            bucket = "user-uploads"

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{fname}",
                    headers={
                        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
                        "Content-Type": mime,
                        "x-upsert": "true",
                    },
                    content=img_bytes,
                )
                if resp.status_code in (200, 201):
                    public_url = f"{config.SUPABASE_URL}/storage/v1/object/public/{bucket}/{fname}"
                    logger.info("uploaded temp image to Supabase: %s (%d bytes)", public_url, len(img_bytes))
                    return public_url
                else:
                    logger.warning("Supabase upload failed, trying tmpfiles.org fallback. Status: %s", resp.status_code)
        except Exception as e:
            logger.warning("Supabase upload error, trying tmpfiles.org fallback: %s", e)

    # Fallback to tmpfiles.org
    try:
        ext = "png" if "png" in mime else "jpg"
        fname = f"temp_tryon_{uuid.uuid4().hex[:8]}.{ext}"
        async with httpx.AsyncClient(timeout=30) as client:
            files = {"file": (fname, img_bytes, mime)}
            resp = await client.post("https://tmpfiles.org/api/v1/upload", files=files)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    viewer_url = data["data"]["url"]
                    if "tmpfiles.org/" in viewer_url:
                        dl_url = viewer_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                        logger.info("uploaded temp image to tmpfiles.org: %s", dl_url)
                        return dl_url
            raise RuntimeError(f"tmpfiles.org upload failed: {resp.text}")
    except Exception as e:
        logger.exception("Failed to upload temp image to any backend")
        raise RuntimeError(f"All temporary image upload backends failed. Detail: {e}")



# ── Runflow Backend (FREE $10 credit — Nano Banana 2 + GPT Image 2) ──────

_RUNFLOW_MODELS = {
    "nano_banana": "google/nano-banana-2/edit",
    "gpt_image_2": "openai/gpt-image-2/edit",
}
_RUNFLOW_POLL_INTERVAL = 2.5
_RUNFLOW_POLL_MAX_WAIT = 120


async def _runflow_generate(
    prompt: str,
    reference_image_path: Optional[str] = None,
    is_tryon: bool = False,
    model_key: str = "nano_banana",
    extra_image_urls: list[str] | None = None,
) -> str:
    """Generate/edit image via Runflow API (supports multiple models)."""
    api_key = config.RUNFLOW_API_KEY
    if not api_key:
        raise RuntimeError("RUNFLOW_API_KEY not configured")

    model_path = _RUNFLOW_MODELS.get(model_key, _RUNFLOW_MODELS["nano_banana"])
    run_url = f"https://api.runflow.io/v1/models/{model_path}/runs"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Build image_urls — Runflow needs publicly accessible URLs
    image_urls: list[str] = []
    if reference_image_path:
        img_bytes, mime = await _resolve_image_path(reference_image_path)
        public_url = await _upload_to_temp_url(img_bytes, mime)
        image_urls.append(public_url)
    if extra_image_urls:
        image_urls.extend(extra_image_urls)

    payload: dict = {
        "input": {
            "prompt": prompt,
            "image_urls": image_urls,
            "num_images": 1,
            "output_format": "png",
        }
    }

    # Model-specific params
    if model_key == "nano_banana":
        payload["input"]["safety_tolerance"] = "4"
        payload["input"]["limit_generations"] = True
    elif model_key == "gpt_image_2":
        payload["input"]["quality"] = "medium"
        payload["input"]["image_size"] = "auto"

    async with httpx.AsyncClient(timeout=150) as client:
        logger.info("runflow %s: posting payload=%s", model_key, payload)
        resp = await client.post(run_url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("runflow %s: %s - %s", model_key, resp.status_code, resp.text[:500])
        resp.raise_for_status()
        run_data = resp.json()
        run_id = run_data.get("id")

        if not run_id:
            raise RuntimeError(f"Runflow returned no run ID: {run_data}")

        logger.info("runflow %s: run=%s submitted", model_key, run_id)

        # Poll for completion
        poll_url = f"https://api.runflow.io/v1/runs/{run_id}"
        start = time.time()
        while time.time() - start < _RUNFLOW_POLL_MAX_WAIT:
            await asyncio.sleep(_RUNFLOW_POLL_INTERVAL)
            status_resp = await client.get(poll_url, headers=headers)
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status = status_data.get("status_code") or status_data.get("status")

            if status in ("succeeded", "completed"):
                output = status_data.get("output", {})
                outputs = output.get("outputs", []) if isinstance(output, dict) else []
                if outputs and outputs[0].get("url"):
                    image_url = outputs[0]["url"]
                    img_resp = await client.get(image_url, timeout=30)
                    img_resp.raise_for_status()
                    return _save_image(img_resp.content, is_tryon, ".png")
                raise RuntimeError(f"Runflow completed but no image URL: {output}")

            elif status in ("failed", "cancelled"):
                error = (
                    status_data.get("failure_message")
                    or status_data.get("error")
                    or "Unknown error"
                )
                raise RuntimeError(f"Runflow run failed: {error}")

            elif status in ("queued", "processing", "running", "in_progress"):
                continue

        raise RuntimeError(f"Runflow run {run_id} timed out after {_RUNFLOW_POLL_MAX_WAIT}s")


# ── RunPod FLUX.1 Kontext Backend ─────────────────────────────────────────

_RUNPOD_BASE = "https://api.runpod.ai/v2"
_POLL_INTERVAL = 2.0
_POLL_MAX_WAIT = 90


async def _runpod_flux_kontext(
    prompt: str,
    reference_image_path: Optional[str] = None,
    is_tryon: bool = False,
    size: str = "1024*1024",
) -> str:
    """Generate/edit image using FLUX.1 Kontext [dev] via RunPod serverless."""
    api_key = config.RUNPOD_API_KEY
    if not api_key:
        raise RuntimeError("RUNPOD_API_KEY not configured")

    endpoint = config.RUNPOD_FLUX_KONTEXT_ENDPOINT
    run_url = f"{_RUNPOD_BASE}/{endpoint}/run"
    status_url_base = f"{_RUNPOD_BASE}/{endpoint}/status"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "input": {
            "prompt": prompt,
            "size": size,
            "num_inference_steps": 28,
            "guidance": 2.5,
            "seed": -1,
            "output_format": "png",
            "enable_safety_checker": True,
        }
    }

    # Add reference image if provided (try-on needs this)
    if reference_image_path:
        img_bytes, mime = await _resolve_image_path(reference_image_path)
        image_url = await _upload_to_temp_url(img_bytes, mime)
        payload["input"]["image"] = image_url

    async with httpx.AsyncClient(timeout=120) as client:
        # Submit job
        resp = await client.post(run_url, headers=headers, json=payload)
        resp.raise_for_status()
        job = resp.json()
        job_id = job.get("id")

        if not job_id:
            raise RuntimeError(f"RunPod returned no job ID: {job}")

        logger.info("runpod flux_kontext: job=%s submitted", job_id)

        # Poll for completion
        start = time.time()
        while time.time() - start < _POLL_MAX_WAIT:
            await asyncio.sleep(_POLL_INTERVAL)
            status_resp = await client.get(
                f"{status_url_base}/{job_id}", headers=headers
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status = status_data.get("status")

            if status == "COMPLETED":
                output = status_data.get("output", {})
                if isinstance(output, dict):
                    image_url = output.get("image_url") or output.get("result")
                elif isinstance(output, str):
                    image_url = output
                else:
                    image_url = None
                if not image_url:
                    raise RuntimeError(f"RunPod completed but no image URL: {output}")

                # Download the result image
                img_resp = await client.get(image_url, timeout=30)
                img_resp.raise_for_status()
                return _save_image(img_resp.content, is_tryon, ".png")

            elif status == "FAILED":
                error = status_data.get("error", "Unknown error")
                raise RuntimeError(f"RunPod job failed: {error}")

            elif status in ("IN_QUEUE", "IN_PROGRESS"):
                continue
            else:
                logger.warning("runpod: unknown status %s", status)

        raise RuntimeError(f"RunPod job {job_id} timed out after {_POLL_MAX_WAIT}s")


# ── Gemini Backend ──────────────────────────────────────────────────────────

async def _gemini_generate(
    prompt: str,
    reference_image_path: Optional[str] = None,
    is_tryon: bool = False,
) -> str:
    """Generate image using Google Gemini API (google-genai SDK)."""
    import os
    from google import genai
    from google.genai import types

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

    api_key = config.GOOGLE_API_KEY or config.GOOGLE_API_KEY_2
    if not api_key:
        raise RuntimeError("No GOOGLE_API_KEY configured")

    client = genai.Client(api_key=api_key)
    model = config.GEMINI_IMAGE_MODEL

    contents: list = []
    if reference_image_path:
        img_bytes, mime = await _resolve_image_path(reference_image_path)
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
    contents.append(prompt)

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                ext = ".png" if "png" in part.inline_data.mime_type else ".jpg"
                return _save_image(part.inline_data.data, is_tryon, ext)

    raise RuntimeError("Gemini returned no image data")


# ── OpenAI GPT Image Backend ───────────────────────────────────────────────

async def _openai_generate(
    prompt: str,
    reference_image_path: Optional[str] = None,
    is_tryon: bool = False,
) -> str:
    """Generate image using OpenAI's gpt-image-1 model."""
    from openai import OpenAI as SyncOpenAI

    client = SyncOpenAI(api_key=config.OPENAI_API_KEY)

    if reference_image_path:
        local_ref = await _resolve_to_local_file(reference_image_path)

        def _do_edit():
            with open(local_ref, "rb") as img_file:
                return client.images.edit(
                    model="gpt-image-1",
                    image=img_file,
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                    quality="low",
                )

        result = await asyncio.to_thread(_do_edit)
        if local_ref != reference_image_path:
            Path(local_ref).unlink(missing_ok=True)
    else:
        result = await asyncio.to_thread(
            client.images.generate,
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="low",
            response_format="b64_json",
        )

    if result.data and len(result.data) > 0:
        img_data = result.data[0]
        if hasattr(img_data, "b64_json") and img_data.b64_json:
            image_bytes = base64.b64decode(img_data.b64_json)
        elif hasattr(img_data, "url") and img_data.url:
            import requests
            resp = requests.get(img_data.url, timeout=30)
            resp.raise_for_status()
            image_bytes = resp.content
        else:
            raise RuntimeError("OpenAI returned no image data")
        return _save_image(image_bytes, is_tryon)

    raise RuntimeError("OpenAI image generation returned no results")


# ── Dispatcher ──────────────────────────────────────────────────────────────

async def generate_image(
    prompt: str,
    reference_image_path: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    is_tryon: bool = False,
    extra_image_urls: list[str] | None = None,
) -> str:
    """Unified image generation dispatcher.

    Models:
        nano_banana      - Nano Banana 2 via Runflow (FREE, $0.08/img)
        gpt_image_2      - GPT Image 2 via Runflow (FREE, $0.133/img)
        flux_kontext     - FLUX.1 Kontext 1080p ($0.025/img) — best try-on
        flux_kontext_720 - FLUX.1 Kontext 720p ($0.025/img) — fast try-on
        gptimage         - OpenAI GPT Image 1 ($0.02/img, paid key)
        gemini           - Google Gemini Flash (quota-limited)

    Returns:
        URL-routable path to saved image (e.g. "data/tryon/tryon_abc.png").
    """
    model = model.lower().strip()

    logger.info("generate_image: model=%s tryon=%s prompt=%s...", model, is_tryon, prompt[:80])

    if model == "nano_banana":
        return await _runflow_generate(prompt, reference_image_path, is_tryon, "nano_banana", extra_image_urls)
    elif model == "gpt_image_2":
        return await _runflow_generate(prompt, reference_image_path, is_tryon, "gpt_image_2", extra_image_urls)
    elif model == "flux_kontext":
        return await _runpod_flux_kontext(
            prompt, reference_image_path, is_tryon, size="1080*1080"
        )
    elif model == "flux_kontext_720":
        return await _runpod_flux_kontext(
            prompt, reference_image_path, is_tryon, size="720*720"
        )
    elif model == "gptimage":
        return await _openai_generate(prompt, reference_image_path, is_tryon)
    elif model == "gemini":
        return await _gemini_generate(prompt, reference_image_path, is_tryon)
    else:
        logger.warning("Unknown model %s, falling back to nano_banana", model)
        return await _runflow_generate(prompt, reference_image_path, is_tryon, "nano_banana")
