"""Query rewriter — resolves pronouns, context, and implicit filters using Groq.

Runs BEFORE the planner. Takes raw user message + conversation history and produces
a self-contained, explicit query the planner can handle without needing to reason
about multi-turn context.

Example: history has "show me shirts" → "for my wife" → "in blue"
Rewriter output: "blue women's shirt"
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import httpx

from api import config

logger = logging.getLogger(__name__)

_CACHE: dict[str, str] = {}
_CACHE_MAX = 500
_PRODUCT_HINT_RE = re.compile(
    r"\b(product|products|shirt|t\s*shirt|tshirt|jeans|kurti|clothes|clothing|"
    r"wear|laptop|keyboard|speaker|camera|sunglasses|bag|sprite|drink|drinks|"
    r"beverage|food|eat|snack|snacks|pringles|electronics)\b",
    re.IGNORECASE,
)
_GREETING_REWRITE_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|yo+|namaste|namaskar)\s*[!.?]*\s*$",
    re.IGNORECASE,
)
_REJECTION_RE = re.compile(
    r"^\s*(no+|nah|nope|na+h*|not?\s+thanks?|no\s+thanks?)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

_SYSTEM = """You are a query rewriter for an ecommerce shopping assistant.

Your job: take the user's latest message and recent conversation history, then produce
a SINGLE self-contained search query that captures the full intent.

Rules:
- Resolve all pronouns and references ("that one", "the blue one", "for my wife", "same but cheaper")
- Carry forward gender context: if user said "for my wife/girlfriend/her" → add "women's" or "ladies"
- Carry forward color/size/category from prior turns when user is refining
- If the message is already clear, specific, and self-contained (especially if there is no history), output it completely unchanged. Do not add or change anything.
- Never expand simple search terms into lists of categories (e.g. do NOT rewrite "shirts" to "men's and women's shirts", keep it as "shirts").
- Keep it simple, clean, and direct. Output ONLY the query.

Examples:
History: "show me shirts" → assistant showed men's and women's shirts
User: "for my wife"
Output: women's shirt

History: "show shirts for my wife" → assistant showed women's shirt
User: "do you have in blue?"
Output: blue women's shirt

History: (none)
User: "show me laptops under 50000"
Output: laptops under 50000

History: "recommend something for gaming"
User: "what about a keyboard?"
Output: gaming keyboard
"""


async def rewrite_query(
    raw_message: str,
    history_lines: list[str],
) -> str:
    """Rewrite user message using Groq for context resolution.

    Falls back to raw_message on any error.
    """
    if not config.GROQ_API_KEY:
        return raw_message

    # Skip rewriting for simple rejections (no, nope, nah, no thanks)
    if _REJECTION_RE.match(raw_message):
        return raw_message

    cache_key = hashlib.sha256(
        f"{'|'.join(history_lines[-6:])}||{raw_message}".encode()
    ).hexdigest()[:16]

    if cache_key in _CACHE:
        logger.debug("rewriter cache hit")
        return _CACHE[cache_key]

    history_text = "\n".join(history_lines[-6:])
    user_prompt = f"History:\n{history_text}\n\nUser's latest message: {raw_message}"

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 60,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        rewritten = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .strip('"\'')
        )

        if not rewritten:
            return raw_message
        if _PRODUCT_HINT_RE.search(raw_message) and _GREETING_REWRITE_RE.match(rewritten):
            logger.info(
                "rewriter rejected product-to-greeting rewrite: %r -> %r",
                raw_message,
                rewritten,
            )
            return raw_message

        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[cache_key] = rewritten

        logger.info("rewriter: %r → %r", raw_message, rewritten)
        return rewritten

    except Exception as e:
        logger.warning("rewriter failed, using raw query: %s", e)
        return raw_message
