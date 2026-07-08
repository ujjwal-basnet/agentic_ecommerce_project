"""OpenAI LLM wrapper via pydantic-ai + Gemini image generation.

- Text/reasoning: OpenAI (via pydantic-ai)
- Image generation: Google Gemini via google-genai SDK (NOT Vertex AI)
- Embeddings: handled by Pinecone's integrated embedding (llama-text-embed-v2)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from tenacity import retry, stop_after_attempt, wait_exponential

from api import config

logger = logging.getLogger(__name__)

# pydantic-ai reads OPENAI_API_KEY from the environment; mirror it.
if config.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = config.OPENAI_API_KEY

# Handle custom LLM providers (vLLM, Ollama, etc.)
if getattr(config, "LLM_PROVIDER", "openai").lower() in ("openai-compatible", "ollama"):
    os.environ["OPENAI_BASE_URL"] = getattr(config, "LLM_BASE_URL", "http://localhost:8002/v1")
else:
    os.environ.pop("OPENAI_BASE_URL", None)


def _get_model() -> str:
    """Return the pydantic-ai model string, e.g. 'openai:gpt-4o-mini'."""
    return f"openai:{config.OPENAI_MODEL}"


T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=16)
def _cached_agent(system_prompt: str, output_type_name: str, schema: Any) -> Agent:
    """Cache pydantic-ai Agent instances by (system_prompt, schema).

    For structured (schema) outputs we use NativeOutput → the model is asked for
    a JSON object matching the schema via `response_format`, which vLLM enforces
    with guided decoding (xgrammar). This avoids OpenAI tool-calling, which vLLM
    rejects unless started with --tool-call-parser.
    """
    output_type: Any = NativeOutput(schema) if schema is not None else str
    return Agent(_get_model(), output_type=output_type, system_prompt=system_prompt)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def acall_llm(
    system: str,
    user: str,
    *,
    schema: type[BaseModel] | None = None,
) -> BaseModel | str:
    """Primary async LLM call.

    For openai-compatible (local vLLM) providers: uses direct HTTP to avoid
    pydantic-ai's OpenAI client, which fails when Qwen3 returns thinking tokens
    in `reasoning_content` and leaves `content` empty.

    For real OpenAI: delegates to pydantic-ai Agent as before.

    Returns:
        Pydantic model when schema is given, else plain text string.
    """
    if getattr(config, "LLM_PROVIDER", "openai").lower() in ("openai-compatible", "ollama"):
        import asyncio
        import json as _json
        from urllib import request as _urllib_request

        payload: dict = {
            "model": config.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 512,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_object"}

        def _post() -> str:
            base = (getattr(config, "LLM_BASE_URL", "http://localhost:8002/v1") or "").rstrip("/")
            req = _urllib_request.Request(
                f"{base}/chat/completions",
                data=_json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.OPENAI_API_KEY or 'local-dummy-key'}",
                },
                method="POST",
            )
            with _urllib_request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            text: str = data["choices"][0]["message"].get("content") or ""
            # Strip <think>…</think> blocks from Qwen3 thinking mode
            if "</think>" in text:
                text = text[text.rfind("</think>") + len("</think>"):].strip()
            return text

        raw = await asyncio.to_thread(_post)
        if schema is not None:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return schema.model_validate_json(raw[start:end])
            raise ValueError(f"LLM returned no JSON object: {raw[:200]!r}")
        return raw

    # ── Real OpenAI / other pydantic-ai providers ────────────────────────────
    output_name = schema.__name__ if schema is not None else "str"
    agent = _cached_agent(system, output_name, schema)
    result = await agent.run(user)
    return result.output


def call_llm(
    system: str,
    user: str,
    *,
    schema: type[BaseModel] | None = None,
) -> BaseModel | str:
    """Sync wrapper around acall_llm for non-async callers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, acall_llm(system, user, schema=schema))
            return future.result()
    return asyncio.run(acall_llm(system, user, schema=schema))


# ── Image Generation via OpenAI gpt-image-1 ─────────────────────────────────


async def generate_image(
    prompt: str,
    reference_image_path: str | None = None,
) -> str:
    """Generate an image using OpenAI's gpt-image-1 model.

    Args:
        prompt: Text prompt describing the desired image.
        reference_image_path: Optional path to a reference image (e.g., user photo
            for virtual try-on). When provided, uses the edit endpoint.

    Returns:
        The file path to the saved generated image (PNG).
    """
    from openai import OpenAI as SyncOpenAI
    from pathlib import Path
    import base64

    client = SyncOpenAI(api_key=config.OPENAI_API_KEY)

    if reference_image_path:
        output_dir = Path(config.TRYON_DIR)
        prefix = "tryon"
    else:
        output_dir = Path(config.CAMPAIGN_DIR)
        prefix = "campaign"

    output_dir.mkdir(parents=True, exist_ok=True)

    if reference_image_path:
        # Use image edit for try-on (reference image + prompt)
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference image not found: {reference_image_path}")

        result = await asyncio.to_thread(
            client.images.edit,
            model="gpt-image-1",
            image=open(ref_path, "rb"),
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="low",
        )
    else:
        # Standard image generation for campaigns
        result = await asyncio.to_thread(
            client.images.generate,
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="low",
            response_format="b64_json",
        )

    # Extract image data
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

        fname = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
        out_path = output_dir / fname
        out_path.write_bytes(image_bytes)
        logger.info("generate_image: saved %s (%d bytes)", out_path, len(image_bytes))
        url_prefix = "data/tryon" if reference_image_path else "data/campaigns"
        return f"{url_prefix}/{fname}"

    raise RuntimeError("OpenAI image generation returned no results.")
