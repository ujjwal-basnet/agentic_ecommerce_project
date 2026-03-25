"""Single OpenAI client wrapper with retry. Every LLM call goes through here."""

from __future__ import annotations
import logging
from typing import Any
from tenacity import retry, stop_after_attempt, wait_random_exponential
import config

_logger = logging.getLogger(__name__)
_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is None:
        if not config.openai_enabled():
            return None
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.0,
) -> str:
    """Centralized LLM call with automatic retry. Returns raw text."""
    client = _get_client()
    if client is None:
        raise RuntimeError("OpenAI not configured (set OPENAI_API_KEY in .env)")
    response_format = {"type": "json_object"} if json_mode else {"type": "text"}
    resp = client.chat.completions.create(
        model=model or config.OPENAI_MODEL,
        response_format=response_format,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


def call_llm_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """LLM call that returns parsed JSON dict."""
    import json
    raw = call_llm(system_prompt, user_prompt, model=model, json_mode=True)
    return json.loads(raw)


def call_llm_vision(
    system_prompt: str,
    text_prompt: str,
    image_paths: list[str],
    model: str | None = None,
    temperature: float = 0.3,
) -> str:
    """Send images + text to a vision-capable model. Returns text response."""
    import base64, mimetypes
    client = _get_client()
    if client is None:
        raise RuntimeError("OpenAI not configured")

    content_parts: list[dict] = []
    if text_prompt:
        content_parts.append({"type": "text", "text": text_prompt})

    for path in image_paths:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
        })

    resp = client.chat.completions.create(
        model=model or "gpt-4o",
        temperature=temperature,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ],
    )
    return resp.choices[0].message.content.strip()


def generate_image(prompt: str, model: str = "dall-e-3", size: str = "1024x1024") -> bytes:
    """Generate an image via DALL-E and return raw PNG bytes."""
    client = _get_client()
    if client is None:
        raise RuntimeError("OpenAI not configured")

    resp = client.images.generate(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        response_format="b64_json",
    )
    import base64
    return base64.b64decode(resp.data[0].b64_json)
