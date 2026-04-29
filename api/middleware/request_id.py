"""Compatibility import for request-id middleware.

The implementation lives in `observability.request_context` because log context
and request ids are coupled at runtime.
"""

from api.observability.request_context import (
    RequestIdMiddleware,
    current_request_id,
    set_request_id,
)

__all__ = ["RequestIdMiddleware", "current_request_id", "set_request_id"]
