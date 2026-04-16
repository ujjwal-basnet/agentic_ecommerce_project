"""Engine — One entry point for all queries.

Flow: Context enrichment → Plan (LLM #1) → Execute tools (no LLM) → Generate response (LLM #2)
Greetings/small talk: 1 LLM call (planner returns direct_response)
Tool queries: 2 LLM calls (planner + response generator)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

import database
import session_memory
from thread_pool import run_in_thread
from planner import create_plan
from executor import execute_tools
from response_generator import generate_response
from config import PROTOCOL_LOG_PATH

logger = logging.getLogger(__name__)


def _log(event: str, **kwargs):
    record = {"event": event, "ts": datetime.now().isoformat(), **kwargs}
    Path(PROTOCOL_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(PROTOCOL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    logger.info("protocol.%s %s", event, kwargs)


def _build_output(response, tool_results, session_id: str) -> dict:
    """Extract structured data from tool results for frontend rendering."""
    output = {
        "text": response.text,
        "component": response.component,
        "cart_count": database.cart_count(session_id),
        "data": {},
        "products": None,
        "images": None,
    }

    for tr in tool_results:
        if not tr.success:
            continue

        if tr.tool in ("search_products", "get_all_products", "get_products_by_category", "get_product_by_id"):
            output["products"] = tr.data.get("products", [])
            output["data"] = tr.data

        elif tr.tool in ("view_cart", "add_to_cart", "remove_from_cart", "clear_cart"):
            output["data"] = tr.data

        elif tr.tool == "get_weather":
            output["data"] = tr.data

        elif tr.tool == "perform_virtual_try_on":
            if tr.data.get("image_path"):
                output["images"] = [tr.data["image_path"]]
            output["data"] = tr.data

    return output


def _sanitize_text(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s{0,3}[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s{0,3}\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


async def run(
    user_input: str,
    channel: str = "web",
    session_id: str | None = None,
    context: str = "",
    user_image_path: str | None = None,
) -> dict:
    """Process user query end-to-end.

    Flow:
    1. Context enrichment (session memory + chat history)
    2. Plan (LLM call #1) — decides tools + args OR direct_response
    3. Execute tools directly (NO LLM)
    4. Generate response (LLM call #2) — text + UI component
    """
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

        # Phase 1: Context enrichment
        session_memory.update_from_message(session_id, user_input)
        memory_context = session_memory.get_context_string(session_id)
        full_context = "\n".join(part for part in [context, memory_context] if part)
        if user_image_path:
            full_context = "\n".join(
                part for part in [full_context, f"User has uploaded a photo: {user_image_path}"] if part
            )

        # Phase 2: Plan (LLM call #1)
        plan = await run_in_thread(create_plan, user_input, session_id, channel, full_context)

        # If direct response (greeting/small talk) — 1 LLM call total, done
        if plan.direct_response:
            direct_text = _sanitize_text(plan.direct_response)
            database.save_message(session_id, "user", user_input)
            database.save_message(session_id, "assistant", direct_text)
            result = {
                "text": direct_text,
                "cart_count": database.cart_count(session_id),
                "session_id": session_id,
            }
            _log("response", session_id=session_id, text=direct_text[:300],
                 component=None, steps=0, llm_calls=1)
            return result

        tools_used = [tc.tool for tc in plan.tool_calls]
        _log("plan_created", session_id=session_id, intent=plan.intent, tools=tools_used)

        # Phase 3: Execute tools directly (NO LLM)
        tool_results = await execute_tools(plan.tool_calls, session_id, user_image_path)

        # Phase 4: Generate response (LLM call #2)
        response = await run_in_thread(
            generate_response, user_input, tool_results, full_context, channel,
        )

        # Phase 5: Build output
        output = _build_output(response, tool_results, session_id)
        output["text"] = _sanitize_text(output.get("text", ""))
        output["session_id"] = session_id

        database.save_message(session_id, "user", user_input)
        if output["text"]:
            database.save_message(session_id, "assistant", output["text"])

        _log("response", session_id=session_id, text=output["text"][:300],
             component=output.get("component"), tools=tools_used, llm_calls=2)

        return output

    except Exception as exc:
        _log("error", session_id=session_id, message=user_input, error=repr(exc))
        logger.exception("engine.run failed session=%s message=%r", session_id, user_input)
        raise


async def run_text(user_input: str, session_id: str | None = None) -> str:
    """Convenience: run query and return just text. For Facebook, Instagram, etc."""
    result = await run(user_input, channel="text", session_id=session_id)
    return result.get("text", "Sorry, something went wrong.")
