"""
Stage 1 Planner — principle-based, catalog-aware.

The planner sees a flat product index (no categories) from data/products.md 
and reasons from product names, tags, prices, and colors to pick the right IDs. 
"""

from __future__ import annotations

import logging
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib import request as urllib_request

from pydantic_ai import Agent, NativeOutput
from tenacity import retry, stop_after_attempt, wait_exponential

from api import config
from api.engine.schemas import CapabilityPlan
from api.llm import _get_model

logger = logging.getLogger(__name__)

import re

SYSTEM_TEMPLATE = """You are the SmartShop planner.

Return only one valid CapabilityPlan JSON object. Do not include markdown.
Use short descriptions and a concise overall_strategy; do not write hidden
chain-of-thought.

{catalog}

Allowed capabilities:
- resolve_products(product_ids: list[int])
- add_to_cart(product_id: int, quantity: int)
- remove_from_cart(product_id: int)
- view_cart()
- clear_cart()
- checkout_cart()
- perform_virtual_try_on(product_id: int)
- recommend_products(context: str, limit: int)
- search_knowledge_base(query: str)

Routing rules:
- Product browsing, availability, stock, price, comparison, recommendation,
  and "do you have X" requests must use resolve_products with catalog IDs.
- Product queries use exactly one resolve_products step. Never add
  search_knowledge_base beside a product step.
- search_knowledge_base is only for store policy: delivery, shipping, returns,
  refund, payment, warranty, privacy, and sizing.
- Product filters are AND filters. Color, category, item type, gender and price
  constraints must all match. If no catalog item matches a hard constraint,
  return no steps and a short direct_response.
- Use product IDs only from the catalog. Never invent product IDs.
- For web, the renderer will show product cards and answer text later.
- For MCP, Facebook and Instagram, the renderer sends reply_message text only,
  but the planner still emits the same tool calls.
- Direct greetings and pure small talk use no steps and direct_response only.
- Ask for clarification only when cart or try-on target is truly missing.
"""

OLD_ID_TO_NAME_KEYWORD = {
    1: "keyboard",
    2: "harry porter",
    3: "wayfarer",
    4: "pringles",
    5: "royal blue",
    6: "sprite",
    7: "nitro",
    8: "laptop cover bag",
    9: "kurti",
    10: "latitude",
    11: "loq",
    12: "jeans",
    13: "cctv",
    14: "soundbox",
    15: "thunder",
    16: "womens formal shirt",
    17: "power adapter",
    18: "polar fleece",
    19: "dumbbell",
    20: "portable handheld rechargeable fan"
}

def _parse_catalog_from_md() -> list[dict[str, Any]]:
    path = Path("data/products.md")
    if not path.exists():
        return []
    pattern = re.compile(
        r"-\s+id=(\d+)\s+.\s+([^.\n]+?)\s+.\s+Rs\.\s+(\d+)"
        r"\s+.\s+color:\s+([^.\n]+?)\s*(?:.\s+tags:\s+(.+))?$"
    )
    products: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        tags_raw = (match.group(5) or "[]").strip()
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []
        products.append(
            {
                "id": int(match.group(1)),
                "name": match.group(2).strip(),
                "price": int(match.group(3)),
                "color": match.group(4).strip(),
                "tags": tags,
            }
        )
    return products

def _get_id_mapping(products: list[dict[str, Any]]) -> dict[int, int]:
    mapping = {}
    for old_id, keyword in OLD_ID_TO_NAME_KEYWORD.items():
        matched_id = None
        for p in products:
            if keyword in p["name"].lower():
                matched_id = p["id"]
                break
        if matched_id is not None:
            mapping[old_id] = matched_id
    return mapping

def _build_catalog_text() -> str:
    products = _parse_catalog_from_md()
    if not products:
        return "(catalog unavailable)"
    mapping = _get_id_mapping(products)
    wearable_old = (2, 5, 9, 12, 16, 18)
    wearable_new = sorted(mapping[i] for i in wearable_old if i in mapping)
    wearable_str = ", ".join(str(i) for i in wearable_new)
    lines = [
        "Catalog source of truth:",
        f"Wearable product IDs for virtual try-on: {wearable_str}.",
    ]
    for product in products:
        tags = ", ".join(str(tag) for tag in product["tags"][:10])
        lines.append(
            f"- id={product['id']} | {product['name']} | Rs. {product['price']} "
            f"| color: {product['color']} | tags: {tags}"
        )
    return "\n".join(lines)

def _planner_prompt() -> str:
    """Build the system prompt exactly matching the training template."""
    return SYSTEM_TEMPLATE.format(catalog=_build_catalog_text())

@lru_cache(maxsize=1)
def _planner_agent_cached() -> Agent:
    """Agent instance — we inject catalog per call via instructions."""
    return Agent(
        _get_model(),
        output_type=NativeOutput(CapabilityPlan),
        output_retries=3,  # small models need a couple tries to satisfy the schema
    )

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
async def _run_planner(system_prompt: str, user_prompt: str) -> CapabilityPlan:
    if getattr(config, "LLM_PROVIDER", "openai").lower() in ("openai-compatible", "ollama"):
        return await _run_openai_compatible_planner(system_prompt, user_prompt)

    result = await _planner_agent_cached().run(
        user_prompt,
        instructions=system_prompt,
    )
    return result.output


def _extract_json_object(text: str) -> str:
    """Return the first JSON object from a model response.

    Qwen3 can emit `<think>...</think>` unless its chat template disables
    thinking. We pass that flag, but keep this parser tolerant so a partial
    template regression does not break the whole app.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"Planner returned no JSON object: {text[:200]!r}")
    return text[start : end + 1]


def _openai_compatible_payload(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    return {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
        # The LoRA was trained with tokenizer.apply_chat_template(...,
        # enable_thinking=False). vLLM accepts this field and forwards it to the
        # Qwen3 chat template, preventing hidden CoT text from preceding JSON.
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _post_openai_compatible(payload: dict[str, Any]) -> dict[str, Any]:
    base = getattr(config, "LLM_BASE_URL", "http://localhost:8002/v1").rstrip("/")
    req = urllib_request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.OPENAI_API_KEY or 'local-dummy-key'}",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def _run_openai_compatible_planner(
    system_prompt: str,
    user_prompt: str,
) -> CapabilityPlan:
    import asyncio

    payload = _openai_compatible_payload(system_prompt, user_prompt)
    data = await asyncio.to_thread(_post_openai_compatible, payload)
    text = data["choices"][0]["message"]["content"]
    return CapabilityPlan.model_validate_json(_extract_json_object(text))

def _channel_preamble(channel: str, context: str | None = None) -> str:
    surfaces = {
        "web": ("customer_web_chat", "product_card_and_answer"),
        "mcp": ("mcp_chat_tool", "reply_message_only"),
        "facebook": ("facebook_dm", "reply_message_only"),
        "instagram": ("instagram_dm", "reply_message_only"),
    }
    surface, renderer = surfaces[channel]
    lines = [f"Channel: {channel}", f"Surface: {surface}", f"Renderer: {renderer}"]
    if context:
        lines.extend(["Context:", context])
    return "\n".join(lines)

async def create_plan(user_request: str, context: str = "") -> CapabilityPlan:
    """Build a catalog-aware plan for the user request."""
    system_prompt = _planner_prompt()
    user_prompt = f"{_channel_preamble('web', context)}\nUser request: {user_request}"

    try:
        plan = await _run_planner(system_prompt, user_prompt)
        plan.user_request = user_request
        logger.info(
            "planner: steps=%d direct=%s caps=%s",
            len(plan.steps),
            bool(plan.direct_response),
            [s.capability for s in plan.steps],
        )
        return plan
    except Exception as exc:
        logger.exception("Planner failed: %s", exc)
        return CapabilityPlan(
            user_request=user_request,
            steps=[],
            overall_strategy="Fallback due to planner error",
            direct_response="Sorry, I hit a snag. Could you try again?",
        )
