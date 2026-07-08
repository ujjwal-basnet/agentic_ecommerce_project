"""Response text generator.

Two-tier strategy:
1. `_fast_text` — deterministic one-liner for simple product list replies
   (user asked "show me X", no comparison needed). No LLM cost.
2. `generate_text` — LLM fallback when the user asked a question that
   requires reasoning ("which has the highest RAM?", "explain the diff",
   "why this one?").

The planner is the one that decides intent. If the user's query contains a
question marker (which, why, explain, compare, better, difference, tell me,
recommend), we route to the LLM with a compact summary of retrieved
products. Otherwise we short-circuit.
"""

from __future__ import annotations

import logging
import re

from api.engine.schemas import ResolvedPlan, StepStatus
from api.llm import acall_llm

logger = logging.getLogger(__name__)

# Markers that suggest the user wants an explanation or comparison — not
# just a product list. These trigger a short LLM call against the result set.
_QUESTION_MARKERS = re.compile(
    r"\b(which|why|how|explain|compare|compared to|"
    r"better|best|highest|lowest|worst|more|less|difference|differ|"
    r"tell me|recommend|suggest|opinion|think|good|bad|pros|cons|"
    r"vs|versus|between)\b",
    re.IGNORECASE,
)

# Colors the user might mention so we can echo the filter in the reply.
_KNOWN_COLORS = {
    "black", "white", "red", "green", "blue", "yellow", "grey", "gray",
    "silver", "gold", "pink", "purple", "orange", "brown",
}

_COUNT_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

_MD_TOKEN = re.compile(r"(\*\*|__|`)")
_MD_BULLET = re.compile(r"^\s{0,3}[-*\d.]+\s+", re.MULTILINE)
_PRICE_QUESTION_RE = re.compile(
    r"\b(price|cost|how\s+much|rate|rs\.?|nrs|rupees?)\b",
    re.IGNORECASE,
)
_DRINK_QUESTION_RE = re.compile(
    r"\b(can|could|should)\s+i\s+drink\s+(?:this|it|that|one)\b"
    r"|\bis\s+(?:this|it|that|one)\s+(?:drinkable|a\s+drink|a\s+beverage)\b",
    re.IGNORECASE,
)
_BROAD_RECOMMEND_RE = re.compile(
    r"^\s*(?:please\s+)?(?:recommend|suggest|pick)\s+(?:me\s+)?(?:something|products?|items?)\s*[?.!]*\s*$",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    """Strip markdown tokens — we never want bold/bullets in chat bubbles."""
    cleaned = _MD_TOKEN.sub("", text or "")
    cleaned = _MD_BULLET.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _format_rs(value: object) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"Rs. {int(amount):,}"


def _query_color(user_query: str) -> str | None:
    q = (user_query or "").lower()
    for color in sorted(_KNOWN_COLORS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(color)}\b", q):
            return "grey" if color == "gray" else color
    return None



def _looks_like_question(user_query: str) -> bool:
    """Heuristic: does the user expect analysis vs a product list?"""
    q = (user_query or "").strip().lower()
    if not q:
        return False
    # A trailing `?` AND a question marker — both must be present to trigger
    # the LLM call. Just a `?` isn't enough ("anything green?" is still a list).
    has_mark = bool(_QUESTION_MARKERS.search(q))
    return has_mark


def _deterministic_product_text(products: list[dict], user_query: str) -> str:
    """Craft a short, natural one-liner for a product list. No LLM."""
    count = len(products)
    if count == 0:
        return (
            "I couldn't find a matching product. "
            "Try a different color, category, or budget."
        )

    names = [str((p or {}).get("name") or "").strip() for p in products[:3]]
    names = [n for n in names if n]
    joined = _join_names(names)

    color = _query_color(user_query)

    if count == 1:
        if not joined:
            return "Yes, I found one matching product."
        if color:
            return f"Yes, I found this {color} product: {joined}."
        return f"Yes, I found {joined}."

    count_word = _COUNT_WORDS.get(count, str(count))
    label = "products"
    if color:
        label = f"{color} {label}"

    if joined:
        suffix = "" if count <= 3 else f", plus {count - 3} more"
        return f"Yes, I found {count_word} {label}: {joined}{suffix}."
    return f"Yes, I found {count_word} matching {label}."


def _is_drink_product(product: dict) -> bool:
    haystack = " ".join(
        str(product.get(key) or "").lower()
        for key in ("name", "category", "description", "color")
    )
    return bool(
        re.search(
            r"\b(sprite|cola|coke|soda|drink|beverage|juice|water|lemon|lime)\b",
            haystack,
            re.IGNORECASE,
        )
    )


def _attribute_question_text(products: list[dict], user_query: str) -> str | None:
    """Answer direct questions about the returned product cards."""
    if not products:
        return None

    if _PRICE_QUESTION_RE.search(user_query):
        if len(products) == 1:
            product = products[0]
            name = str(product.get("name") or "That product")
            return f"{name} costs {_format_rs(product.get('price'))}."

        parts = [
            f"{p.get('name') or 'Product'}: {_format_rs(p.get('price'))}"
            for p in products[:4]
        ]
        suffix = "" if len(products) <= 4 else f", plus {len(products) - 4} more"
        return "The prices are " + "; ".join(parts) + suffix + "."

    if _DRINK_QUESTION_RE.search(user_query):
        product = products[0]
        name = str(product.get("name") or "This product")
        if _is_drink_product(product):
            return f"Yes, {name} is listed as a drink, so you can drink it."
        return f"No, {name} is not listed as a drink."

    return None


def _broad_recommendation_text(products: list[dict], user_query: str) -> str | None:
    if not _BROAD_RECOMMEND_RE.search(user_query):
        return None
    names = [
        str((product or {}).get("name") or "").strip()
        for product in products[:3]
        if (product or {}).get("name")
    ]
    if not names:
        return "I picked a few options from the catalog for you."
    suffix = "" if len(products) <= 3 else f", plus {len(products) - 3} more"
    return f"I picked a few options from the catalog: {_join_names(names)}{suffix}."


def _compact_product(p: dict) -> dict:
    """Trim a product dict down to fields useful for LLM reasoning."""
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "color": p.get("color"),
        "price": p.get("price"),
        "category": p.get("category"),
        "description": (p.get("description") or "")[:400],
    }



_REASONING_SYSTEM = """You are SmartShop's concierge.

The user asked a question about products returned below. Answer naturally in
1-3 sentences using ONLY the products' name, price, description, and category.
If the user asks "which has highest X" or "which is better for Y", reason from
the descriptions and name the specific product with the key detail.

Rules:
- No markdown, no bullets, no headers. Plain text.
- Be specific: reference the product by name and the concrete detail
  (e.g. "The Acer Nitro has 16GB RAM, same as the Lenovo LOQ, but its
  RTX 5050 8GB is a bigger GPU than the Lenovo's RTX 4050 6GB.").
- If the products don't contain the info, say so honestly.
- Keep it friendly and human — don't list every product.
- Detect the user's language automatically from their query. If the user types in Nepali (romanized or Devanagari) like "ke xa", you MUST reply entirely in Nepali. Never reply in Hindi.
"""


async def generate_response_text(
    plan: ResolvedPlan,
    products: list[dict],
    user_query: str,
) -> str:
    """Return the assistant's text reply for the current turn.

    Short-circuit to a deterministic one-liner when possible. Fall back to
    an LLM call when the user asked a question requiring analysis.
    """
    # Agent-level messages take priority (cart, checkout, knowledge)
    for step in plan.steps:
        if step.status != StepStatus.DONE or not isinstance(step.result, dict):
            continue
        result = step.result

        if step.agent_name == "CartAgent":
            msg = result.get("message")
            if msg:
                return _plain(str(msg))
            # view_cart has no message — generate text from cart data
            action = result.get("action", "")
            if action == "view":
                count = result.get("count") or len(result.get("items") or [])
                if count:
                    return f"Here's your cart with {count} item{'s' if count != 1 else ''}."
                return "Your cart is empty."
            return "Cart updated."

        if step.agent_name == "CheckoutAgent":
            msg = result.get("message")
            if msg:
                return _plain(str(msg))

        if step.agent_name == "TryOnAgent":
            success = result.get("success", False)
            if not success:
                err = result.get("error", "")
                if "user_image_path is required" in err:
                    return "To try this on, please upload a photo of yourself first."
                return _plain(err or "Sorry, virtual try-on failed.")
            product_name = result.get("product_name") or "the product"
            return f"Here is your virtual try-on with the {product_name}!"

        if step.agent_name == "KnowledgeBaseAgent":
            results = result.get("results") or []
            if results:
                top = results[0]
                return _plain(
                    str(
                        top.get("content")
                        or top.get("answer")
                        or top.get("title")
                        or "Here's what I found."
                    )
                )

    # No products? fall back to a generic message
    if not products:
        done = [s for s in plan.steps if s.status == StepStatus.DONE]
        if not done:
            return "I hit an issue processing that. Could you try again?"
        return "I couldn't find a matching product. Try another color or category?"

    broad_recommendation_text = _broad_recommendation_text(products, user_query)
    if broad_recommendation_text:
        return broad_recommendation_text

    attribute_text = _attribute_question_text(products, user_query)
    if attribute_text:
        return attribute_text

    # If the user asked a question, let the LLM reason over the result set.
    if _looks_like_question(user_query):
        try:
            compact = [_compact_product(p) for p in products[:6]]
            user = (
                f"User question: {user_query}\n\n"
                f"Products returned ({len(products)} total, showing up to 6):\n"
                + "\n".join(
                    f"- id={p['id']} | {p['name']} | Rs.{p['price']} | "
                    f"{p['category']} | {p['description']}"
                    for p in compact
                )
            )
            text = await acall_llm(_REASONING_SYSTEM, user)
            return _plain(str(text))
        except Exception as e:
            logger.warning("reasoning text LLM failed: %s", e)
            # Fall through to deterministic text

    return _deterministic_product_text(products, user_query)
