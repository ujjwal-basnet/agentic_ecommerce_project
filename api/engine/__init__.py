"""Engine — one entry point for all queries.

Flow: resolve follow-up → plan → execute tools → text → component from registry
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from api import db as database
from api import llm
from api.engine.planner import create_plan
from api.engine.executor import execute_tools
from api.engine.response import generate_text
from api.registry import get_registry
from api.schemas import QueryResolution
from api.config import PROTOCOL_LOG_PATH
from api.guardrails import filter_model_output, sanitize_user_input

logger = logging.getLogger(__name__)

_QUERY_RESOLUTION_SYSTEM = """You rewrite ecommerce follow-up queries into standalone queries.

Use the recent conversation only when the current query is incomplete.
If the current query is already clear, return it unchanged.

Rules:
- Do not answer the user.
- Do not add products, emotions, life situations, or old topics unless the current query clearly refers to them.
- Do not carry over old breakup/bored/thirsty context into a fresh product query.
- Do not invent product names, product IDs, variants, or colors that are not explicitly stated.
- When the user changes a filter like color, budget, or price, keep the product type/category from history but not the exact previous product name.
- Example: history says "red shirts", current query says "do you have in blue" -> rewritten query "show me blue shirts".
- Preserve the user's current constraints such as category, color, budget, and action.
- Return a rewritten query that the shopping planner can understand without chat history."""


def _log(event: str, **kwargs):
    """Fire-and-forget protocol log — never blocks the response."""
    record = {"event": event, "ts": datetime.now().isoformat(), **kwargs}
    logger.info("protocol.%s %s", event, kwargs)

    async def _write():
        try:

            def _do():
                p = Path(PROTOCOL_LOG_PATH)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")

            await asyncio.to_thread(_do)
        except Exception:
            logger.debug("protocol log write failed", exc_info=True)

    try:
        asyncio.get_running_loop().create_task(_write())
    except RuntimeError:
        pass


def _pick_component(tool_results, channel: str) -> str | None:
    if channel != "web":
        return None
    registry = get_registry()
    for tr in reversed(tool_results):
        if not tr.success:
            continue
        comp = registry.get_component(tr.tool)
        if comp:
            return comp
    return None


def _build_output(text, component, tool_results, session_id: str) -> dict:
    output = {
        "text": text,
        "component": component,
        "cart_count": database.cart_count(session_id),
        "data": {},
        "products": None,
        "images": None,
    }
    for tr in tool_results:
        if not tr.success:
            continue
        if tr.tool in (
            "search_products",
            "get_all_products",
            "get_products_by_category",
            "get_product_by_id",
            "get_products_by_ids",
        ):
            output["products"] = tr.data.get("products", [])
            output["data"] = tr.data
        elif tr.tool in ("view_cart", "add_to_cart", "remove_from_cart", "clear_cart"):
            output["data"] = tr.data
        elif tr.tool == "search_knowledge_base":
            output["data"] = tr.data
        elif tr.tool == "perform_virtual_try_on":
            if tr.data.get("image_path"):
                output["images"] = [tr.data["image_path"]]
            output["data"] = tr.data
    return output


# Words/phrases that signal the query depends on a prior turn.
# Queries with none of these are self-contained — skip the resolver LLM (~800 ms saved).
_FOLLOWUP_PATTERN = re.compile(
    r"\b("
    r"it|that|this|these|those|same|one|ones|previous|last|prior|"
    r"again|another|other|more|less|cheaper|pricier|bigger|smaller|"
    r"instead|rather|also|too|either|"
    r"blue one|red one|green one|black one|white one|yellow one|"
    r"the (first|second|third|last)"
    r")\b",
    re.IGNORECASE,
)


def _needs_resolver(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    if len(q.split()) <= 2:  # Very short — almost always a follow-up ("yes", "blue").
        return True
    return bool(_FOLLOWUP_PATTERN.search(q))


def _sanitize_text(text: str) -> str:
    cleaned = (text or "").replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s{0,3}[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s{0,3}\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _save_messages_async(
    session_id: str, user_input: str, assistant_text: str | None
) -> None:
    """Persist turn messages after the response returns — don't block time-to-last-byte."""

    async def _save():
        try:
            await asyncio.to_thread(
                database.save_message, session_id, "user", user_input
            )
            if assistant_text:
                await asyncio.to_thread(
                    database.save_message, session_id, "assistant", assistant_text
                )
        except Exception:
            logger.exception("save_message failed session=%s", session_id)

    asyncio.create_task(_save())


async def _resolve_query_context(user_input: str, history: str) -> tuple[str, bool]:
    """Use the LLM to turn follow-ups into standalone planner queries."""
    if not history:
        return user_input, False

    user = f"Recent conversation:\n{history}\n\nCurrent query: {user_input}"
    try:
        resolution = await llm.acall_llm(
            _QUERY_RESOLUTION_SYSTEM,
            user,
            schema=QueryResolution,
        )
    except Exception:
        logger.exception("query context resolver failed")
        return user_input, False

    rewritten = (resolution.rewritten_query or user_input).strip()
    return rewritten or user_input, bool(
        resolution.needs_context or rewritten != user_input
    )


async def run(
    user_input: str,
    channel: str = "web",
    session_id: str | None = None,
    context: str = "",
    user_image_path: str | None = None,
) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    database.ensure_session(session_id)

    try:
        _log("user_input", session_id=session_id, message=user_input, channel=channel)

        if not user_input or not user_input.strip():
            return {
                "text": "How can I help you today?",
                "cart_count": database.cart_count(session_id),
                "session_id": session_id,
            }

        # Strip prompt-injection attempts before any LLM call sees the text.
        sanitized = sanitize_user_input(user_input)
        if sanitized.flagged:
            _log(
                "input_flagged",
                session_id=session_id,
                matches=sanitized.matches,
                truncated=sanitized.truncated,
            )
        user_input = sanitized.cleaned or user_input

        turn_start = time.perf_counter()
        timings: dict[str, int] = {}

        def _ms(t0: float) -> int:
            return int((time.perf_counter() - t0) * 1000)

        # Phase 1: Resolve follow-up into a standalone planner query
        history = _get_history_context(session_id, limit=6)
        run_resolver = bool(history) and _needs_resolver(user_input)
        resolver_llm_calls = 1 if run_resolver else 0
        t = time.perf_counter()
        if run_resolver:
            planner_query, used_history = await _resolve_query_context(
                user_input, history
            )
        else:
            planner_query, used_history = user_input, False
        timings["resolver_ms"] = _ms(t)

        planner_context = context
        if used_history and history:
            history_block = (
                f"Recent conversation (last 3 user + 3 assistant):\n{history}"
            )
            planner_context = "\n".join(
                p for p in [planner_context, history_block] if p
            )
        if user_image_path:
            planner_context = "\n".join(
                p
                for p in [planner_context, f"User uploaded photo: {user_image_path}"]
                if p
            )
        lang = detect_language(user_input)
        if lang == "ne":
            planner_context = "\n".join(
                p
                for p in [
                    planner_context,
                    "Language: User is writing in Nepali. Respond in Nepali (Devanagari script preferred, romanized OK).",
                ]
                if p
            )
        if planner_query != user_input:
            _log(
                "query_rewritten",
                session_id=session_id,
                original=user_input,
                rewritten=planner_query,
                used_history=used_history,
            )

        # Phase 2: Plan
        t = time.perf_counter()
        plan = await create_plan(planner_query, session_id, channel, planner_context)
        timings["planner_ms"] = _ms(t)

        if plan.direct_response:
            direct_text = _sanitize_text(plan.direct_response)
            filtered = filter_model_output(direct_text)
            if filtered.flagged:
                _log("output_flagged", session_id=session_id, matches=filtered.matches)
            direct_text = filtered.text
            _save_messages_async(session_id, user_input, direct_text)
            timings["total_ms"] = _ms(turn_start)
            _log(
                "response",
                session_id=session_id,
                text=direct_text[:300],
                steps=0,
                llm_calls=1 + resolver_llm_calls,
                **timings,
            )
            return {
                "text": direct_text,
                "cart_count": database.cart_count(session_id),
                "session_id": session_id,
            }

        tools_used = [tc.tool for tc in plan.tool_calls]
        _log(
            "plan_created", session_id=session_id, intent=plan.intent, tools=tools_used
        )

        # Phase 3: Tools
        t = time.perf_counter()
        tool_results = await execute_tools(plan.tool_calls, session_id, user_image_path)
        timings["tools_ms"] = _ms(t)

        # Phase 4: Text — skipped for product-list tools via _fast_text
        t = time.perf_counter()
        text = await generate_text(user_input, tool_results, channel)
        timings["response_ms"] = _ms(t)
        component = _pick_component(tool_results, channel)

        # Phase 5: Output
        filtered = filter_model_output(_sanitize_text(text))
        if filtered.flagged:
            _log("output_flagged", session_id=session_id, matches=filtered.matches)
        output = _build_output(filtered.text, component, tool_results, session_id)
        output["session_id"] = session_id

        _save_messages_async(session_id, user_input, output["text"] or None)

        timings["total_ms"] = _ms(turn_start)
        _log(
            "response",
            session_id=session_id,
            text=output["text"][:300],
            component=component,
            tools=tools_used,
            llm_calls=2 + resolver_llm_calls,
            **timings,
        )
        return output

    except Exception as exc:
        _log("error", session_id=session_id, message=user_input, error=repr(exc))
        logger.exception(
            "engine.run failed session=%s message=%r", session_id, user_input
        )
        raise


_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_NEPALI_KEYWORDS = {
    "ke",
    "ma",
    "mero",
    "tapai",
    "kasto",
    "ramro",
    "cha",
    "ho",
    "garnu",
    "dinu",
    "hola",
}


def detect_language(text: str) -> str:
    """Detect if user wrote in Nepali (Devanagari or romanized) vs English."""
    if _DEVANAGARI_RE.search(text):
        return "ne"
    words = set(text.lower().split())
    if len(words & _NEPALI_KEYWORDS) >= 2:
        return "ne"
    return "en"


def _get_history_context(session_id: str, limit: int = 8) -> str:
    """Format recent conversation for LLM context (inlined from old session_memory)."""
    rows = database.load_history(session_id, limit=limit)
    if not rows:
        return ""
    lines = []
    for msg in rows:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:200]}")
    return "\n".join(lines)


async def run_text(user_input: str, session_id: str | None = None) -> str:
    result = await run(user_input, channel="text", session_id=session_id)
    return result.get("text", "Sorry, something went wrong.")
