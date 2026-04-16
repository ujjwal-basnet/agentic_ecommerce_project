"""Planner — Pure LLM plan generator. No fallbacks, no if-else."""

from __future__ import annotations

import logging

import llm
from registry import get_registry

logger = logging.getLogger(__name__)


_SYSTEM = """You are the Planner for SmartShop.

Your job: Convert user queries into agent execution plans.

AVAILABLE AGENTS:
{registry}

OUTPUT FORMAT:
Return JSON list of steps. Each step:
{
  "step": 1,
  "agent": "AgentName",
  "reason": "why this step",
  "input": {"key": "value"}
}

RULES:
1. Use MINIMUM steps needed
2. Chain steps with $$STEP_N_OUTPUT$$ to reference prior output
3. Greetings/chitchat → return empty list []
4. Never invent agents — use only from list above
"""


def create_plan(query: str, session_id: str, channel: str = "web", context: str = "") -> list[dict]:
    """Generate plan using LLM. No fallbacks — if LLM fails, returns empty plan."""
    registry = get_registry()
    registry_text = "\n".join(
        f"- {a['agent']}: {a['description']}" for a in registry.tool_registry()
    )

    system = _SYSTEM.format(registry=registry_text)
    user = f"Session: {session_id}\nChannel: {channel}\nQuery: {query}"
    if context:
        user = f"Context: {context}\n{user}"

    try:
        plan = llm.call_llm(system, user, json_output=True)
        if not isinstance(plan, list):
            logger.warning(f"Planner returned non-list: {type(plan)}")
            return []

        for step in plan:
            inp = step.get("input", {})
            inp["session_id"] = session_id
            inp["channel"] = channel
            step["input"] = inp

        # Append WriterAgent if not present
        if plan and plan[-1].get("agent") != "WriterAgent":
            last_num = plan[-1].get("step", len(plan))
            plan.append({
                "step": last_num + 1,
                "agent": "WriterAgent",
                "reason": "Format final output for channel",
                "input": {
                    "session_id": session_id,
                    "channel": channel,
                    "original_query": query,
                    "prev_output": f"$$STEP_{last_num}_OUTPUT$$",
                },
            })

        return plan

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        return []  # Empty plan = no action

