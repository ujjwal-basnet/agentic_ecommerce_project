"""Planner — LLM call that decides intent + tool calls."""

from __future__ import annotations
import logging

import llm
from registry import get_registry
from schemas import PlannerOutput

logger = logging.getLogger(__name__)
_SYSTEM = """Planner for SmartShop. Pick the user's intent and the smallest safe tool plan.

CATALOG (product index — the only valid source of product IDs; never invent them):
{catalog}

TOOLS:
{registry}

Principles:
- Default to doing, not asking. If the user is browsing, curious, or wants a recommendation, pick IDs from the Catalog and call get_products_by_ids. Only ask a short clarification for cart/try-on/account actions where the target is truly ambiguous.
- Open recommendations ("recommend me something", "suggest products", "what's new"): reason — don't memorize a fixed list. Lean on the Context's "Recent conversation" block (last 3 user + 3 assistant turns) to bias toward what the user has talked about, looked at, or bought. If recent turns give no signal, return a diverse 4–6 item mix spanning categories and price points.
- Vary your picks turn-to-turn. If the user repeats "recommend something", don't return the identical list — rotate in Catalog items they haven't seen yet.
- Respect explicit constraints literally (budget, color, category, wearable, in-stock). Any hard constraints baked into the Catalog header (e.g. wearable-only IDs) apply automatically.
- Budget/filter queries ("under 2000", "below 500", "cheap shirts", "red", "in stock"): scan the Catalog and return EVERY ID that matches the constraint (up to 6–8 items), spread across different categories and price points. Do NOT return only the 1–2 cheapest items — the user wants to see the full range of what's available within their budget.
- Use recent conversation to resolve references like "that one" or "same budget", and to personalize recommendations. Don't carry over unrelated prior topics when the user clearly shifts subject.
- Cart actions: use add_to_cart/remove_from_cart/view_cart/clear_cart. Pass product_id when the Catalog or recent context makes it clear.
- Try-on: when a user photo is present and the product is wearable, call perform_virtual_try_on directly. Ask only when photo or product is missing.
- Stock/availability questions: call get_products_by_ids — the payload carries live `quantity`.
- Greetings and pure small talk with no product intent: direct_response only.
- Keep tool_calls minimal (1–2 tools max)."""

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
