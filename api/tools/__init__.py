"""LangChain tool package."""

from api.tools.products import (
    get_all_products,
    get_product_by_id,
    get_products_by_category,
    get_products_by_ids,
    search_products,
)
from api.tools.cart import add_to_cart, checkout_cart, clear_cart, remove_from_cart, view_cart
from api.tools.history import get_user_history
from api.tools.knowledge import search_knowledge_base
from api.tools.tryon import perform_virtual_try_on

PRODUCT_TOOLS = [search_products, get_products_by_ids]
PRODUCT_HELPERS = [get_all_products, get_product_by_id, get_products_by_category]
CART_TOOLS = [view_cart, add_to_cart, remove_from_cart, clear_cart, checkout_cart]
CONTEXT_TOOLS = [get_user_history]
KB_TOOLS = [search_knowledge_base]
TRY_ON_TOOLS = [perform_virtual_try_on]
ALL_TOOLS = PRODUCT_TOOLS + CART_TOOLS + CONTEXT_TOOLS + KB_TOOLS + TRY_ON_TOOLS

__all__ = [
    "get_all_products",
    "get_product_by_id",
    "get_products_by_category",
    "get_products_by_ids",
    "search_products",
    "add_to_cart",
    "checkout_cart",
    "clear_cart",
    "remove_from_cart",
    "view_cart",
    "get_user_history",
    "search_knowledge_base",
    "perform_virtual_try_on",
    "PRODUCT_TOOLS",
    "PRODUCT_HELPERS",
    "CART_TOOLS",
    "CONTEXT_TOOLS",
    "KB_TOOLS",
    "TRY_ON_TOOLS",
    "ALL_TOOLS",
]
