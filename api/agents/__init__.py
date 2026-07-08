"""
Specialist agent entry points and ecommerce agent registry builder.

Provides `build_ecommerce_registry()` which creates an AgentRegistry populated
with all ecommerce domain agents (ProductSearch, Cart, KnowledgeBase, TryOn,
Recommendation, Checkout).

Usage:
    from api.agents import get_agent_registry
    registry = get_agent_registry()
"""
from __future__ import annotations

from api.agent_registry import AgentCard, AgentRegistry
from api.agents.cart_agent import cart_impl
from api.agents.checkout_agent import checkout_impl
from api.agents.knowledge import knowledge_base_impl
from api.agents.product_search import product_search_impl
from api.agents.recommendation import recommendation_impl
from api.agents.resolve_products import resolve_products_impl
from api.agents.tryon_agent import tryon_impl


# ── Registry builder ─────────────────────────────────────────────────────


def build_ecommerce_registry() -> AgentRegistry:
    """
    Create an AgentRegistry and register all ecommerce domain agents.

    Each agent declares its capabilities, input schema, UI component hint,
    and tags. Implementations call real agent logic from api/agents/ modules.
    """
    registry = AgentRegistry()

    registry.register(AgentCard(
        name="ProductSearchAgent",
        capabilities=["search_products", "find_products", "browse_products", "filter_products"],
        description="Searches products by semantic query and/or structured filters (price, category, color).",
        input_schema={
            "query": "str (optional) - semantic search query",
            "max_price": "float (optional) - price ceiling",
            "category": "str (optional) - product category filter",
            "color": "str (optional) - color filter",
            "limit": "int (default 8) - max results",
        },
        impl=product_search_impl,
        tags=["product", "search", "rag"],
        component="ProductList",
    ))

    registry.register(AgentCard(
        name="ResolveProductsAgent",
        capabilities=["resolve_products", "get_products_by_ids", "show_products"],
        description=(
            "Fetch full product records by ID. Preferred over search_products "
            "when the planner already knows which products match."
        ),
        input_schema={"product_ids": "list[int] - IDs from the catalog"},
        impl=resolve_products_impl,
        tags=["product", "lookup"],
        component="ProductList",
    ))

    registry.register(AgentCard(
        name="CartAgent",
        capabilities=["add_to_cart", "remove_from_cart", "view_cart", "clear_cart"],
        description="Manages shopping cart operations.",
        input_schema={
            "action": "str - one of: add, remove, view, clear",
            "product_id": "int (optional) - product to add/remove",
            "quantity": "int (default 1)",
            "session_id": "str (auto-injected)",
        },
        impl=cart_impl,
        tags=["cart", "shopping"],
        component="CartConfirmation",
    ))

    registry.register(AgentCard(
        name="KnowledgeBaseAgent",
        capabilities=["search_knowledge_base", "answer_faq", "store_policy"],
        description="Answers FAQ and policy questions from the knowledge base.",
        input_schema={"query": "str - the question or topic"},
        impl=knowledge_base_impl,
        tags=["knowledge", "faq", "policy"],
        component=None,
    ))

    registry.register(AgentCard(
        name="TryOnAgent",
        capabilities=["perform_virtual_try_on", "try_on_clothing"],
        description="Performs virtual try-on using Gemini image generation.",
        input_schema={
            "product_id": "int - product to try on",
            "user_image_path": "str - path to user's photo",
        },
        impl=tryon_impl,
        tags=["tryon", "image", "clothing"],
        component=None,
    ))

    registry.register(AgentCard(
        name="RecommendationAgent",
        capabilities=["recommend_products", "suggest_products", "personalize"],
        description="Provides personalized product recommendations using RAG.",
        input_schema={
            "session_id": "str (auto-injected)",
            "context": "str (optional) - user preferences/history",
            "limit": "int (default 6)",
        },
        impl=recommendation_impl,
        tags=["recommendation", "personalization"],
        component="RecommendGrid",
    ))

    registry.register(AgentCard(
        name="CheckoutAgent",
        capabilities=["checkout_cart", "place_order", "complete_purchase"],
        description="Places an order from the current cart.",
        input_schema={"session_id": "str (auto-injected)"},
        impl=checkout_impl,
        tags=["checkout", "order"],
        component="CartConfirmation",
    ))

    return registry


# ── Module-level singleton ───────────────────────────────────────────────

_REGISTRY: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """
    Return the module-level singleton AgentRegistry.

    Lazily builds the registry on first call. Thread-safe for typical
    single-threaded async usage (FastAPI event loop).
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_ecommerce_registry()
    return _REGISTRY
