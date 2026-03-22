"""Structured MCP logger — writes every event to logs/mcp_log.jsonl."""

import json
from datetime import datetime
from config import MCP_LOG_PATH


def log_event(event: str, **kwargs) -> None:
    record = {"event": event, "ts": datetime.now().isoformat(), **kwargs}
    with open(MCP_LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def log_user_input(session_id, message, role="customer"):
    log_event("user_input", session_id=session_id, message=message, role=role)


def log_plan(session_id, agent, tool, step_count=1):
    log_event("plan_created", session_id=session_id, agent=agent,
              tool=tool, step_count=step_count)


def log_agent_call(session_id, agent, tool, input_keys):
    log_event("agent_call", session_id=session_id, agent=agent,
              tool=tool, input_keys=input_keys)


def log_agent_result(session_id, agent, tool, status, latency_ms, result_count=None):
    log_event("agent_result", session_id=session_id, agent=agent, tool=tool,
              status=status, latency_ms=latency_ms, result_count=result_count)


def log_render(session_id, tool, ui_component):
    log_event("render_decision", session_id=session_id, tool=tool,
              ui_component=ui_component,
              output_type="genui" if ui_component else "text")


def log_sse(session_id, event_type, component=None):
    log_event("sse_emitted", session_id=session_id,
              type=event_type, component=component)


def log_error(session_id, agent, error, attempt):
    log_event("agent_error", session_id=session_id, agent=agent,
              error=str(error)[:300], attempt=attempt)


def log_error_fatal(session_id, agent, user_message):
    log_event("agent_error_fatal", session_id=session_id,
              agent=agent, user_message=user_message)


def log_direct_cart(session_id, product_name, action="add"):
    log_event("direct_cart_add", session_id=session_id,
              product_name=product_name, action=action)
