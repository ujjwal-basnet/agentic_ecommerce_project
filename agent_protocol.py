"""MCP Protocol + AgentRegistry — SmartShop."""

import json
import copy
import importlib
import time
import logging
from datetime import datetime
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


def create_mcp_message(sender: str, content: dict, metadata: dict = None) -> dict:
    return {
        "protocol_version": "1.0 (SmartShop)",
        "sender": sender,
        "content": content,
        "metadata": metadata or {
            "timestamp": datetime.now().isoformat(),
            "session_id": None,
            "agent": None,
            "tool": None,
            "latency_ms": None,
            "ui_component": None,
        },
    }


def resolve_dependencies(input_params: dict, state: dict) -> dict:
    """Replace $$STEP_X_OUTPUT$$ tokens with values from executor state."""
    resolved = copy.deepcopy(input_params)

    def _r(v):
        if isinstance(v, str) and v.startswith("$$") and v.endswith("$$"):
            key = v[2:-2]
            if key not in state:
                raise ValueError(f"Missing: {key}. Have: {list(state)}")
            return state[key]
        if isinstance(v, dict):
            return {k: _r(val) for k, val in v.items()}
        if isinstance(v, list):
            return [_r(i) for i in v]
        return v

    return _r(resolved)


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Callable] = {}

    def register(self, name: str, handler: Callable) -> None:
        self._agents[name] = handler

    def get_handler(self, agent_name: str, llm=None,
                    session_id: str = None) -> Callable:
        handler = self._agents.get(agent_name)
        if not handler:
            raise ValueError(f"'{agent_name}' not found. Have: {list(self._agents)}")

        def tracked(msg: dict, **kwargs) -> dict:
            t = time.time()
            try:
                call_kwargs = {}
                if llm:
                    call_kwargs["llm"] = llm
                call_kwargs.update(kwargs)
                result = handler(msg, **call_kwargs)
            except Exception as e:
                result = create_mcp_message(
                    agent_name,
                    {"status": "error", "error": str(e),
                     "tool": msg.get("content", {}).get("tool", "unknown")},
                )
            result.setdefault("metadata", {})
            result["metadata"].update(
                latency_ms=int((time.time() - t) * 1000),
                agent=agent_name,
                session_id=session_id,
            )
            return result

        return tracked

    def capabilities(self) -> str:
        return """
1. SearchAgent    — search_products_tool, virtual_try_on
2. CartAgent      — add_to_cart, view_cart, remove_from_cart, apply_discount, clear_cart
3. RecommendAgent — recommend
4. WeatherAgent   — get_weather
5. OwnerAgent     — add_product, update_product, delete_product,
                    get_analytics, post_to_facebook, get_embeddings_status
"""

    def list(self) -> list[str]:
        return list(self._agents.keys())


_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry:
        return _registry
    _registry = AgentRegistry()

    def _load(mod: str, cls: str):
        return getattr(importlib.import_module(f"agents.{mod}"), cls)().handle

    _registry.register("SearchAgent", _load("search", "SearchAgent"))
    _registry.register("CartAgent", _load("cart", "CartAgent"))
    _registry.register("RecommendAgent", _load("recommend", "RecommendAgent"))
    _registry.register("WeatherAgent", _load("weather", "WeatherAgent"))
    _registry.register("OwnerAgent", _load("owner", "OwnerAgent"))
    _registry.register("TryOnAgent", _load("tryon", "TryOnAgent"))
    return _registry
