"""Response Generator — produces the user-facing TEXT only.

UI component selection lives in the registry (single source of truth).
This module generates text from tool results — nothing else.
"""

from __future__ import annotations

import json
import logging
import re

import llm
from schemas import ToolResult

logger = logging.getLogger(__name__)

_MAX_LIST_ITEMS = 6
_MAX_TEXT_CHARS = 400

# Tools that return {"products": [...]} — the UI renders a grid, so text is a one-liner.
_PRODUCT_TOOLS = {
    "search_products",
    "get_all_products",
    "get_products_by_category",
    "get_product_by_id",
    "get_products_by_ids",
}

_SYSTEM = """Write a short SmartShop reply using only the current user query and tool results.

Rules:
- Do not use previous conversation or old topics.
- Do not mention emotions, breakup, boredom, Sprite, Pringles, or Nepali slang unless the current user query or current tool results directly mention them.
- If products are returned, summarize only those returned products.
- If a tool failed, apologize briefly.
- Keep it focused, natural, and 1-3 sentences.
- Output plain text only. No markdown, bullets, headings, or code blocks."""


_MD_TOKEN = re.compile(r"(\*\*|__|`)")
_MD_BULLET = re.compile(r"^\s{0,3}[-*\d.]+\s+", re.MULTILINE)


def _plain(text: str) -> str:
    cleaned = _MD_TOKEN.sub("", text or "")
    cleaned = _MD_BULLET.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _compact(v):
    if isinstance(v, dict):
        return {k: _compact(x) for k, x in v.items()}
    if isinstance(v, list):
        out = [_compact(x) for x in v[:_MAX_LIST_ITEMS]]
        if len(v) > _MAX_LIST_ITEMS:
            out.append({"omitted_count": len(v) - _MAX_LIST_ITEMS})
        return out
    if isinstance(v, str) and len(v) > _MAX_TEXT_CHARS:
        return v[:_MAX_TEXT_CHARS] + "..."
    return v


def _product_list_text(tool: str, data: dict) -> str | None:
    """Synthesize a one-liner for product-list turns — the UI renders the grid, text is decoration."""
    products = data.get("products")
    if not isinstance(products, list):
        return None
    count = len(products)
    if count == 0:
        return "No products matched that — try a different category or budget."
    if tool == "get_product_by_id" or count == 1:
        name = (products[0] or {}).get("name") if products else None
        return f"Here's {name}." if name else "Here's what I found."
    return f"Here are {count} options for you."


def _fast_text(tool_results: list[ToolResult]) -> str | None:
    """Skip the LLM when tool output already carries a ready-to-show message."""
    if not tool_results:
        return None

    failed = [tr for tr in tool_results if not tr.success]
    if failed and len(failed) == len(tool_results):
        return _plain(f"Sorry, that didn't work: {failed[0].error or 'unknown error'}")

    last_ok = next((tr for tr in reversed(tool_results) if tr.success), None)
    if not last_ok:
        return None

    data = last_ok.data or {}
    text = data.get("text") or data.get("message")
    if text:
        return _plain(str(text))

    # Skip LLM for product-list turns — synthesize a one-liner, UI renders the grid.
    if last_ok.tool in _PRODUCT_TOOLS:
        synth = _product_list_text(last_ok.tool, data)
        if synth:
            return _plain(synth)

    return None


async def generate_text(
    user_query: str,
    tool_results: list[ToolResult],
    channel: str = "web",
) -> str:
    """Return the assistant's text reply. No component logic here."""
    fast = _fast_text(tool_results)
    if fast:
        logger.info("response_generator fast len=%d", len(fast))
        return fast

    parts = []
    for tr in tool_results:
        status = "OK" if tr.success else f"FAIL: {tr.error}"
        parts.append(
            f"{tr.tool} [{status}]: "
            f"{json.dumps(_compact(tr.data), separators=(',', ':'))}"
        )
    results_text = "\n".join(parts)

    user_parts = [f"Query: {user_query}", f"Results:\n{results_text}"]
    user = "\n\n".join(user_parts)

    text = await llm.acall_llm(_SYSTEM, user)
    text = _plain(text)
    logger.info("response_generator llm len=%d", len(text))
    return text
