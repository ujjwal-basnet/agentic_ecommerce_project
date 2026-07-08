"""
Agent registry. Maps CAPABILITY names to concrete agent implementations.

Two access patterns:
  - exact: get_by_capability("search_products") → list[AgentCard]
  - semantic: search_by_capability("find items") → ranked AgentCards
                (used as fallback when planner invents a capability name
                 that doesn't exactly match any registered capability)

In production this would use a database (Postgres + pgvector) or service
(Consul, etcd, or a dedicated agent-discovery service). Hot-reloadable so
new agents come online without restarting the planner.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class AgentCard:
    """Describes a single agent's identity, capabilities, and implementation."""

    name: str  # e.g. "ProductSearchAgent"
    capabilities: list[str]  # e.g. ["search_products", "find_products"]
    description: str
    input_schema: dict[str, Any]  # JSON-schema-style hint for what params the agent needs
    impl: Callable[..., Awaitable[Any]] | None = None  # async callable
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    component: str | None = None  # Frontend UI component hint (e.g. "ProductList")
    _embedding: list[float] | None = field(default=None, repr=False)


def _embed(text: str, dim: int = 64) -> list[float]:
    """
    Simple hash-based embedding for semantic search fallback.

    Uses SHA-256 to produce a deterministic pseudo-embedding vector.
    In production this would call OpenAI text-embedding-3-small.
    """
    h = hashlib.sha256(text.lower().encode()).digest()
    vec: list[float] = []
    for i in range(dim):
        b = h[i % len(h)]
        # Bonus for token presence at this dimension
        token_bonus = sum(1 for w in text.lower().split() if hash(w) % dim == i)
        vec.append((b / 255.0) + 0.1 * token_bonus)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two unit vectors."""
    return sum(x * y for x, y in zip(a, b))


class AgentRegistry:
    """
    Registry that maps capability names to AgentCard instances.

    Supports exact O(1) lookup by name or capability, plus a semantic
    fallback using embedding similarity when exact match fails.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, AgentCard] = {}
        self._by_capability: dict[str, list[AgentCard]] = {}

    def register(self, card: AgentCard) -> None:
        """Register an agent card, computing its embedding for semantic search."""
        text = (
            f"{card.name} {card.description} "
            f"{' '.join(card.capabilities)} {' '.join(card.tags)}"
        )
        card._embedding = _embed(text)
        self._by_name[card.name] = card
        for cap in card.capabilities:
            self._by_capability.setdefault(cap, []).append(card)

    def get_by_name(self, name: str) -> AgentCard:
        """Exact name lookup. Raises KeyError if not found."""
        if name not in self._by_name:
            raise KeyError(f"No agent named {name!r}")
        return self._by_name[name]

    def get_by_capability(self, capability: str) -> list[AgentCard]:
        """Exact capability lookup (O(1) via dict). Returns all agents that claim it."""
        return list(self._by_capability.get(capability, []))

    def search_by_capability(self, capability: str, k: int = 5) -> list[AgentCard]:
        """
        Semantic fallback using embedding similarity.

        Used when an exact capability lookup fails — the planner may have used
        a slightly different verb (e.g. 'check_identity' vs registered
        'verify_identity'). We embed the capability string and find the closest
        registered agents by cosine similarity.
        """
        if not self._by_name:
            return []
        q = _embed(capability)
        scored = [(_cosine(q, c._embedding or []), c) for c in self._by_name.values()]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]

    def get_planner_prompt_text(self) -> str:
        """
        Generate a TOOLS section for the planner prompt automatically from
        registered agents.
        """
        lines = []
        for name, card in sorted(self._by_name.items()):
            # Use the primary capability
            cap = card.capabilities[0] if card.capabilities else "unknown"
            
            # Format input schema 
            schema_parts = []
            for k, v in card.input_schema.items():
                if "auto-injected" not in str(v).lower():
                    schema_parts.append(f"{k} ({str(v).split(' - ')[0]})")
            
            params = f"{{ {', '.join(schema_parts)} }}" if schema_parts else "none"
            lines.append(f"- {cap:<17} — params: {params}")
            if card.description:
                # Add description on the next line, indented
                lines.append(f"  {card.description}")
        return "\n".join(lines)
