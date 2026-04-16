"""Response Generator — single LLM call to format tool results into a user response."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import llm
from schemas import ResponseGeneratorOutput, ToolResult

logger = logging.getLogger(__name__)

_PRODUCT_TOOLS = {"search_products", "get_product_by_id", "get_products_by_category"}
_CART_TOOLS = {"view_cart", "add_to_cart", "remove_from_cart", "clear_cart"}
_RECOMMEND_WORDS = ("recommend", "suggest", "best", "for me", "what should")
_MAX_PROMPT_LIST_ITEMS = 8
_MAX_PROMPT_TEXT_CHARS = 600


_SYSTEM = """You are the response writer for SmartShop, a friendly ecommerce assistant.

Given the user's query and tool execution results, write a helpful response.

RULES:
- Be concise, warm, and helpful (1-3 sentences typically)
- If products were found, briefly mention what was found (don't list every detail — the UI shows that)
- If cart was updated, confirm the action clearly
- If weather was fetched, summarize it naturally
- If a tool failed, apologize and explain briefly
- If recommendation data is available, give personalized suggestions
- Output plain text only. Do not use markdown, asterisks, bullets, headings, or code blocks.

COMPONENT SELECTION — pick the right UI component:
- "ProductList" → when showing search results or products by category
- "CartDrawer" → when showing/modifying cart (add, remove, view, clear)
- "RecommendGrid" → when showing recommendations
- "WeatherCard" → when showing weather information
- null → when no special UI is needed (e.g., simple confirmations)

Channel is "{channel}". {channel_instruction}
"""

_CHANNEL_INSTRUCTIONS = {
    "web": "Use rich formatting. The frontend will render the UI component you choose.",
    "text": "Keep it plain text only. Set component to null — no UI components for text channels.",
}


def _component_for_channel(component: str | None, channel: str) -> str | None:
    return component if channel == "web" else None


def _plain_text(text: str) -> str:
    """Normalize model output to plain text (no markdown styling tokens)."""
    cleaned = text.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s{0,3}[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s{0,3}\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _count_products(data: dict[str, Any]) -> int:
    products = data.get("products", [])
    if isinstance(products, list):
        return len(products)
    return 1 if data.get("id") and data.get("name") else 0


def _looks_like_recommendation(query: str, tool_names: set[str]) -> bool:
    query_l = query.lower()
    return "get_user_preferences" in tool_names or any(word in query_l for word in _RECOMMEND_WORDS)


def _fast_response(
    user_query: str,
    tool_results: list[ToolResult],
    channel: str,
) -> ResponseGeneratorOutput | None:
    successful = [tr for tr in tool_results if tr.success]
    if not successful:
        first_error = next((tr.error for tr in tool_results if tr.error), None)
        text = f"Sorry, I couldn't complete that. {first_error}" if first_error else "Sorry, I couldn't complete that."
        return ResponseGeneratorOutput(text=_plain_text(text), component=None)

    if len(successful) != len(tool_results):
        return None

    tool_names = {tr.tool for tr in successful}

    for tr in reversed(successful):
        if tr.tool in _CART_TOOLS:
            data = tr.data
            text = data.get("text") or data.get("message") or "Cart updated."
            component = "CartDrawer" if tr.tool == "view_cart" else "CartConfirmation"
            return ResponseGeneratorOutput(
                text=_plain_text(text),
                component=_component_for_channel(component, channel),
            )

    weather = next((tr for tr in reversed(successful) if tr.tool == "get_weather"), None)
    if weather:
        data = weather.data
        loc = data.get("location", "your location")
        temp = data.get("temperature")
        condition = data.get("weather", "weather")
        text = data.get("text") or f"Weather in {loc}: {condition}, {temp}C."
        return ResponseGeneratorOutput(
            text=_plain_text(text),
            component=_component_for_channel("WeatherCard", channel),
        )

    product_result = next((tr for tr in reversed(successful) if tr.tool in _PRODUCT_TOOLS), None)
    all_products = next((tr for tr in reversed(successful) if tr.tool == "get_all_products"), None)
    if product_result or all_products:
        tr = product_result or all_products
        count = _count_products(tr.data)
        is_recommendation = _looks_like_recommendation(user_query, tool_names)
        component = "RecommendGrid" if is_recommendation else "ProductList"
        if count:
            text = (
                f"Here are {count} recommendations."
                if is_recommendation
                else f"I found {count} product(s) for you."
            )
        else:
            text = "I couldn't find matching products."
            component = None
        return ResponseGeneratorOutput(
            text=_plain_text(text),
            component=_component_for_channel(component, channel),
        )

    tryon = next((tr for tr in reversed(successful) if tr.tool == "perform_virtual_try_on"), None)
    if tryon:
        text = tryon.data.get("message") or tryon.data.get("text") or "Your try-on image is ready."
        return ResponseGeneratorOutput(text=_plain_text(text), component=None)

    return None


def _compact_for_prompt(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _compact_for_prompt(item) for key, item in value.items()}
    if isinstance(value, list):
        compact = [_compact_for_prompt(item) for item in value[:_MAX_PROMPT_LIST_ITEMS]]
        if len(value) > _MAX_PROMPT_LIST_ITEMS:
            compact.append({"omitted_count": len(value) - _MAX_PROMPT_LIST_ITEMS})
        return compact
    if isinstance(value, str) and len(value) > _MAX_PROMPT_TEXT_CHARS:
        return value[:_MAX_PROMPT_TEXT_CHARS] + "..."
    return value


def generate_response(
    user_query: str,
    tool_results: list[ToolResult],
    context: str = "",
    channel: str = "web",
) -> ResponseGeneratorOutput:
    """Generate the final user-facing response from tool results.

    This is LLM call #2 (the only one besides the planner).
    """
    fast = _fast_response(user_query, tool_results, channel)
    if fast is not None:
        logger.info("response_generator fast text_len=%d component=%s", len(fast.text), fast.component)
        return fast

    # Build tool results summary
    results_parts = []
    for tr in tool_results:
        status = "SUCCESS" if tr.success else f"FAILED: {tr.error}"
        results_parts.append(
            f"Tool: {tr.tool} [{status}]\nData: "
            f"{json.dumps(_compact_for_prompt(tr.data), separators=(',', ':'))}"
        )
    results_text = "\n\n".join(results_parts)

    channel_instruction = _CHANNEL_INSTRUCTIONS.get(channel, _CHANNEL_INSTRUCTIONS["text"])
    system = _SYSTEM.format(channel=channel, channel_instruction=channel_instruction)

    user_parts = []
    if context:
        user_parts.append(f"Context:\n{context}")
    user_parts.append(f"User query: {user_query}")
    user_parts.append(f"Tool results:\n{results_text}")
    user_msg = "\n\n".join(user_parts)

    result = llm.call_llm(system, user_msg, schema=ResponseGeneratorOutput)
    result.text = _plain_text(result.text)
    if channel != "web":
        result.component = None
    logger.info("response_generator text_len=%d component=%s", len(result.text), result.component)
    return result
