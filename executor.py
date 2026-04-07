"""Executor — runs each plan step through the MCP registry."""

import copy
import time
from typing import Any

from channels.capabilities import (
    ChannelCapabilities,
    WEB_APP,
    should_send_component,
)
from custom_mcp import create_mcp_message, resolve_dependencies, get_registry
from log import log_agent_call, log_agent_result, log_error
import database


def execute_plan(
    plan: list[dict[str, Any]],
    session_id: str,
    user_input: str = "",
    user_image_path: str | None = None,
    trace_id: str | None = None,
    channel_caps: ChannelCapabilities | None = None,
) -> dict[str, Any]:
    """Run each step, return consolidated result for the renderer.

    Args:
        plan: Execution plan from orchestrator
        session_id: User session identifier
        user_input: Original user message
        user_image_path: Optional path to uploaded image
        trace_id: Optional trace identifier for logging
        channel_caps: Channel capabilities (defaults to WEB_APP if not provided)

    Returns:
        Dict with text, data, component (if supported), cart count, etc.
    """
    if channel_caps is None:
        channel_caps = WEB_APP

    registry = get_registry()
    state: dict[str, Any] = {}
    total_elapsed = 0.0

    if plan:
        plan = copy.deepcopy(plan)
        plan[0]["input"].setdefault("session_id", session_id)
        plan[0]["input"].setdefault("user_image_path", user_image_path)
        plan[0]["input"].setdefault("channel_caps", channel_caps)

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
            # Pass channel_caps to handler if it accepts it
            import inspect
            sig = inspect.signature(handler)
            if "channel_caps" in sig.parameters:
                mcp_out = handler(mcp_in, channel_caps=channel_caps)
            else:
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

    # Filter component based on channel capabilities
    component = last.get("component")
    if component and not should_send_component(channel_caps):
        component = None

    result = {
        "text": last.get("text", "Here you go!"),
        "component": component,
        "tool": tool,
        "data": data,
        "cart_count": database.cart_count(session_id),
        "steps": len(plan),
        "elapsed": round(total_elapsed, 3),
        "channel": channel_caps.name,
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
