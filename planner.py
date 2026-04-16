"""Planner — LLM planner that returns structured tool calls."""

from __future__ import annotations

import logging

import llm
from registry import get_registry
from schemas import PlannerOutput

logger = logging.getLogger(__name__)


_SYSTEM = """You are the Planner for SmartShop.

Your job: decide intent and tool calls for each user query.

AVAILABLE TOOLS:
{registry}

OUTPUT FORMAT:
Return a JSON object with this shape:
{{
  "intent": "smalltalk|shopping|cart|weather|tryon|other",
  "direct_response": "string or null",
  "tool_calls": [
    {{"tool": "tool_name", "args": {{"key": "value"}}}}
  ]
}}

RULES:
1. Greetings/chitchat: set direct_response and keep tool_calls empty.
2. Tool tasks: keep direct_response null and fill tool_calls.
3. Never invent tools — use only from list above.
4. Keep tool_calls minimal and relevant.
"""


def create_plan(
    query: str,
    session_id: str,
    channel: str = "web",
    context: str = "",
) -> PlannerOutput:
    """Generate a structured execution plan from user input."""
    registry = get_registry()
    registry_text = registry.get_planner_prompt_text()

    system = _SYSTEM.format(registry=registry_text)
    user_parts = []
    if context:
        user_parts.append(f"Context:\n{context}")
    user_parts.append(f"Session: {session_id}")
    user_parts.append(f"Channel: {channel}")
    user_parts.append(f"Query: {query}")
    user_msg = "\n\n".join(user_parts)

    try:
        plan = llm.call_llm(system, user_msg, schema=PlannerOutput)
        logger.info(
            "plan session=%s intent=%s direct=%s tools=%s",
            session_id,
            plan.intent,
            bool(plan.direct_response),
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
