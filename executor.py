"""Executor — runs each plan step through the MCP registry."""

import copy
import time
from typing import Any
from mcp import create_mcp_message, resolve_dependencies, get_registry
from log import log_agent_call, log_agent_result, log_error
import database


def execute_plan(
    plan: list[dict[str, Any]],
    session_id: str,
    user_input: str = "",
    user_image_path: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Run each step, return consolidated result for the renderer."""
    registry = get_registry()
    state: dict[str, Any] = {}
    total_elapsed = 0.0

    if plan:
        plan = copy.deepcopy(plan)
        plan[0]["input"].setdefault("session_id", session_id)
        plan[0]["input"].setdefault("user_image_path", user_image_path)

    for step in plan:
        step_num = step.get("step", 0)
        agent_name = step.get("agent", "")
        raw_input = step.get("input", {})

        try:
            resolved = resolve_dependencies(raw_input, state)
        except Exception as exc:
            log_error(session_id, agent_name, str(exc), attempt=0)
            return _err(str(exc), step_num)

        mcp_in = create_mcp_message("executor", resolved)
        log_agent_call(session_id, agent_name, resolved.get("action", ""),
                       list(resolved.keys()))

        try:
            handler = registry.get_handler(agent_name, session_id=session_id)
        except ValueError as exc:
            log_error(session_id, agent_name, str(exc), attempt=0)
            return _err(str(exc), step_num)

        t0 = time.time()
        try:
            mcp_out = handler(mcp_in)
        except Exception as exc:
            log_error(session_id, agent_name, str(exc), attempt=1)
            mcp_out = create_mcp_message(agent_name, {
                "status": "error", "error": str(exc),
                "text": "An error occurred.", "component": None,
            })

        elapsed = time.time() - t0
        total_elapsed += elapsed
        content = mcp_out.get("content", {})
        log_agent_result(session_id, agent_name, content.get("tool", ""),
                         content.get("status", "ok"), int(elapsed * 1000))

        state[f"STEP_{step_num}_OUTPUT"] = content

    last = state.get(f"STEP_{len(plan)}_OUTPUT", {}) if plan else {}
    tool = last.get("tool", "")
    # Use 'is not None' checks so empty lists [] are preserved (not skipped as falsy)
    data = last.get("data") if last.get("data") is not None else (
        last.get("products") if last.get("products") is not None else (
            last.get("items") if last.get("items") is not None else last
        )
    )

    result = {
        "text": last.get("text", "Here you go!"),
        "component": last.get("component"),
        "tool": tool,
        "data": data,
        "cart_count": database.cart_count(session_id),
        "steps": len(plan),
        "elapsed": round(total_elapsed, 3),
    }

    database.save_message(session_id, "user", user_input)
    database.save_message(session_id, "assistant", result["text"])
    return result


def _err(error: str, step: int) -> dict[str, Any]:
    return {
        "text": f"Something went wrong at step {step}: {error}",
        "component": None, "data": None, "tool": None,
        "cart_count": 0, "steps": step - 1, "elapsed": 0.0,
    }
