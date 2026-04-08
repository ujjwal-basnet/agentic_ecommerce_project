"""Logging package — structured MCP event logger.

Re-exports everything from logs.logger so callers can do:
    from logs import log_event, log_user_input, ...
"""

from logs.logger import (
    log_event,
    log_user_input,
    log_plan,
    log_agent_call,
    log_agent_result,
    log_render,
    log_sse,
    log_error,
    log_direct_cart,
)

__all__ = [
    "log_event",
    "log_user_input",
    "log_plan",
    "log_agent_call",
    "log_agent_result",
    "log_render",
    "log_sse",
    "log_error",
    "log_direct_cart",
]
