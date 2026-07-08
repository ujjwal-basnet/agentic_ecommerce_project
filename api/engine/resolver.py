"""Prompt Resolver — grounding stage between rewriter and planner.

Sits AFTER the rewriter and BEFORE the planner.
Takes the (already rewritten) query + conversation history and produces:

  1. A precise, self-contained intent the planner can act on directly.
     e.g. "great great" + history "showed shirts" → "show shirts" (repeat or new search)
          "show me more"  + history "showed shirts" → "show more shirts"
          "in blue"       + history "showed shirts" → "blue shirt"

  2. The sentinel "__ACK__" when the turn is purely an acknowledgement /
     positive reaction with NO new shopping intent (e.g. "great!", "nice",
     "wow that's amazing"). This short-circuits the planner so no spurious
     product search is triggered.

Design goals:
- Eliminates hallucinations caused by the planner receiving vague/empty intent.
- Prevents duplicate product cards caused by the planner re-running product
  agents on turns that should be conversational short-circuits.
- Inexpensive: uses Groq with a 60-token cap and a 6-turn history window.
- Graceful degradation: any failure returns the raw rewritten query.
"""

from __future__ import annotations

import hashlib
import logging
import re

import httpx

from api import config

logger = logging.getLogger(__name__)

# ── Cache ──────────────────────────────────────────────────────────────────────
_CACHE: dict[str, str] = {}
_CACHE_MAX = 500

# ── System prompt ──────────────────────────────────────────────────────────────
_SYSTEM = """\
You are an intent resolver for an ecommerce shopping assistant called SmartShop.

You receive:
1. A conversation history (up to 6 recent turns, oldest first).
2. The user's current message (already rewritten for pronouns and context).

Your job: determine the PRECISE shopping intent of this turn and output ONE of:

A) __ACK__
   Output this exact sentinel (no other text) when the user's message is a pure
   positive acknowledgement with ZERO new shopping intent.
   Examples that trigger __ACK__:
   - "great", "nice", "wow", "great great", "cool!", "nice nice", "awesome!",
     "perfect", "yay", "👍", "ok thanks", "thanks!", "noted", "got it"
   CRITICAL: NEVER return __ACK__ if the user mentions a product, category,
   or asks for recommendations (e.g., "show me shirts", "recommend something",
   "I want some tshirts"). Those are new intents.

B) A self-contained shopping intent string (plain text, max 15 words).
   Combine the rewritten message with context from history to produce a query
   the planner can act on without ambiguity.
   Examples:
   - History showed shirts, user says "show me more" → "show more shirts"
   - History showed shirts, user says "in blue" → "blue shirt"
   - History showed women's shirts, user says "do you have red?" → "red women's shirt"
   - No history, user says "show me laptops under 50000" → "laptops under 50000"
   - User says "what's in my cart?" → "view cart"

Rules:
- Output ONLY __ACK__ or the resolved query. Nothing else. No explanation. No quotes.
- If the rewritten message already is clear and self-contained, output it unchanged.
- Never invent products or add constraints the user didn't mention.
- Detect user language: if they typed in Nepali, output in Nepali.
"""


async def resolve_prompt(
    rewritten: str,
    history_lines: list[str],
) -> str:
    """Resolve rewritten query into a precise planner intent.

    Returns ``"__ACK__"`` for pure acknowledgements (callers must handle this).
    Falls back to ``rewritten`` on any error.
    """
    # Fast-path: no Groq key → passthrough
    if not config.GROQ_API_KEY:
        return rewritten

    # Build cache key
    cache_key = hashlib.sha256(
        f"resolver|{'|'.join(history_lines[-6:])}||{rewritten}".encode()
    ).hexdigest()[:16]

    if cache_key in _CACHE:
        logger.debug("resolver cache hit key=%s", cache_key)
        return _CACHE[cache_key]

    history_text = "\n".join(history_lines[-6:])
    user_prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"User's current message: {rewritten}"
    ) if history_text else f"User's current message: {rewritten}"

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
                    "temperature": 0.0,
                    "max_tokens": 60,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        resolved = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .strip('"\'')
        )

        if not resolved:
            return rewritten

        # Normalise: collapse whitespace, strip trailing punctuation from non-ACK
        if resolved != "__ACK__":
            resolved = re.sub(r"\s+", " ", resolved).strip().rstrip(".")

        # Guard: if resolver somehow returns a greeting for a product query, ignore it
        _GREETING_RE = re.compile(
            r"^(hi+|hello+|hey+|yo+|namaste|namaskar)\s*[!.?]*$", re.IGNORECASE
        )
        _PRODUCT_HINT_RE = re.compile(
            r"\b(product|shirt|tshirt|jeans|kurti|laptop|speaker|bag|drink|snack)\b",
            re.IGNORECASE,
        )
        if (
            resolved != "__ACK__"
            and _GREETING_RE.match(resolved)
            and _PRODUCT_HINT_RE.search(rewritten)
        ):
            logger.info(
                "resolver rejected greeting rewrite: %r → %r", rewritten, resolved
            )
            return rewritten

        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[cache_key] = resolved

        logger.info("resolver: %r → %r", rewritten, resolved)
        return resolved

    except Exception as exc:
        logger.warning("resolver failed, using rewritten query: %s", exc)
        return rewritten
