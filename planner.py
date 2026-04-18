"""Planner — LLM call that decides intent + tool calls."""

from __future__ import annotations
import logging

import llm
from registry import get_registry
from schemas import PlannerOutput

logger = logging.getLogger(__name__)
_SYSTEM = """Planner for SmartShop. Pick intent and the smallest safe tool plan.

CATALOG (primary product index; use ids from here):
{catalog}

TOOLS:
{registry}

Rules:
- Greetings/chitchat: direct_response only.
- Current user constraints override recent conversation. Use recent conversation only to resolve clear references like "that one", "second one", or "same budget"; do not carry over previous product topics unless the user asks for them.
- For any product browsing, advice, recommendation, category, color, budget, or filter request, resolve matching Catalog IDs from products.md and call get_products_by_ids([...]).
- Treat "wear", "wearable", "clothes", "clothing", and "outfit" as a hard clothing constraint. Only return clothing/wearable Catalog items. Do not include drinks, snacks, electronics, or accessories unless the user explicitly asks for that accessory.
- Apply budget and price constraints strictly. "Under 1000" means every selected product must cost <= 1000.
- Example: "something to wear under 1000" -> get_products_by_ids([6, 9]).
- Do not use search_products, get_all_products, or get_products_by_category for normal product matching. products.md is the product index; use get_products_by_ids with the IDs you selected from it.
- For "show everything" or "all products", call get_products_by_ids with all Catalog IDs.
- Cart actions: use add_to_cart/remove_from_cart/view_cart/clear_cart. Pass product_id only when the product is clear from the Catalog or recent context; otherwise ask a short clarification with direct_response.
- Try-on: for clothing (tshirt/shirt/jeans/kurti), call perform_virtual_try_on with product_id directly when a user photo is available; ask for the missing photo/product when needed.
- Never invent product IDs. Only use IDs from the Catalog.
- Keep tool_calls minimal (1-2 tools max)."""

async def create_plan(
    query: str,
    session_id: str,
    channel: str = "web",
    context: str = "",
) -> PlannerOutput:
    registry = get_registry()
    system = _SYSTEM.format(
        catalog=registry.get_product_catalog_text() or "(catalog unavailable)",
        registry=registry.get_planner_prompt_text(),
    )

    parts = []
    if context:
        parts.append(f"Context:\n{context}")
    parts.append(f"Channel: {channel}\nQuery: {query}")
    user = "\n\n".join(parts)

    try:
        plan = await llm.acall_llm(system, user, schema=PlannerOutput)
        logger.info(
            "plan session=%s intent=%s direct=%s tools=%s",
            session_id, plan.intent, bool(plan.direct_response),
            [tc.tool for tc in plan.tool_calls],
        )
        return plan
    except Exception as exc:
        logger.exception("Planner failed session=%s", session_id)
        return PlannerOutput(
            intent="fallback",
            direct_response=f"Sorry, I hit a planner error: {exc}",
            tool_calls=[],
        )
