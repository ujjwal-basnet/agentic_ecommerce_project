"""Orchestrator — classify intent → build plan → hand off to executor."""

import re
from typing import Any
import config
from llm import call_llm
from log import log_event, log_plan


class Intent:
    SEARCH = "search"
    CART = "cart"
    REC = "rec"
    WEATHER = "weather"
    TRYON = "tryon"
    OWNER = "owner"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"
    ALL = {"search", "cart", "rec", "weather", "tryon", "owner", "chitchat", "unknown"}


_RULE_MAP: dict[tuple[str, ...], str] = {
    ("view cart", "show cart", "open cart", "my cart", "check cart", "whats in my cart"): "cart",
    ("recommend", "suggest", "for you", "you might like", "similar"): "rec",
    ("weather", "temperature", "forecast", "humidity", "climate"): "weather",
    ("try on", "virtual try", "fit on", "wear it"): "tryon",
    ("owner", "dashboard", "analytics", "inventory", "sales", "admin"): "owner",
    ("hi", "hello", "namaste", "howdy", "hey", "how are you"): "chitchat",
}

_SEARCH_KW = (
    "search", "find", "show", "look", "do you have", "i want", "looking for",
    "any", "available", "stock", "price", "cheap", "expensive", "under",
    "red", "blue", "black", "white", "green", "navy", "rato", "nilo", "kalo",
    "tshirt", "t-shirt", "shirt", "saree", "sari", "dress", "jacket", "denim",
    "jeans", "kurti", "kurta", "sunglasses", "glasses", "shades", "chasma",
    "clothes", "clothing", "wear", "product", "item", "accessories",
    "frock", "gown", "polo", "formal", "casual",
)


def classify_intent(user_input: str, context: str = "") -> str:
    if config.openai_enabled():
        try:
            intent = _llm_intent(user_input, context)
            log_event("intent_classified", method="llm", intent=intent, user_input=user_input[:200])
            return intent
        except Exception:
            pass
    intent = _rule_intent(user_input)
    log_event("intent_classified", method="rule", intent=intent, user_input=user_input[:200])
    return intent


def _rule_intent(msg: str) -> str:
    m = msg.lower().strip()
    if " to cart" in m or " to basket" in m or " into cart" in m:
        return Intent.CART
    for keywords, intent in _RULE_MAP.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", m) for kw in keywords):
            return intent
    if any(kw in m for kw in _SEARCH_KW):
        return Intent.SEARCH
    return Intent.UNKNOWN


def _llm_intent(user_input: str, context: str) -> str:
    history_block = ""
    if context:
        history_block = f"""

Recent conversation context:
{context}
Use this context to understand references. For example, if the user previously talked about a product and now says "show me" or "that one", classify as "search"."""

    system = f"""You are an intent classifier for an e-commerce AI shopping assistant called SmartShop.
Classify the user message into ONE of these intents ONLY:
- search: ANY mention of products, clothing, items, colors, categories, prices, availability, stock, "do you have", "show me", "find", "I want", "looking for", "that one", "it". This includes tshirt, shirt, dress, jacket, sari, sunglasses, accessories, or ANY product-related query. Also includes follow-up references to products discussed earlier (e.g. "show me" after asking about sari).
- cart: adding to cart, viewing cart, removing items, updating quantities, "my cart", "checkout"
- rec: recommendations, suggestions, "what should I buy", "suggest something"
- weather: weather, temperature, forecast, climate
- tryon: virtual try-on, "try on", "how does it look on me"
- owner: admin tasks, analytics, inventory, sales dashboard
- chitchat: ONLY pure greetings or casual conversation with NO product/shopping intent (e.g. "hi", "hello", "how are you", "thanks", "bye")

IMPORTANT: If the user mentions ANY product name, clothing type, color, asks about availability, OR if the message is a follow-up to a product discussion (like "show me", "that one", "how much"), classify as "search" NOT "chitchat".
Examples: "do you have tshirts" → search, "show me red shirts" → search, "what clothes do you sell" → search, "show me" (after discussing sari) → search
{history_block}
Return ONLY the intent word in lowercase."""
    resp = call_llm(system, user_input, temperature=0).strip().lower()
    return resp if resp in Intent.ALL else Intent.UNKNOWN


def build_plan(user_input: str, intent: str, mcp: bool = False) -> list[dict[str, Any]]:
    plan = _build_plan_inner(user_input, intent, mcp)
    if plan:
        log_plan("", plan[0].get("agent", ""), intent, len(plan))
    else:
        log_event("plan_empty", intent=intent, user_input=user_input[:200])
    return plan


def _build_plan_inner(user_input: str, intent: str, mcp: bool = False) -> list[dict[str, Any]]:
    if intent == Intent.SEARCH:
        return [{"step": 1, "agent": "SearchAgent",
                 "input": {"query": user_input, "filters": None, "mcp": mcp}}]

    if intent == Intent.CART:
        action = _infer_cart_action(user_input)
        inp: dict[str, Any] = {"action": action, "product_name": None,
                                "price": None, "quantity": None, "mcp": mcp}
        if action in ("add", "update", "remove"):
            inp["product_name"] = _extract_product_name(user_input)
            if action == "add":
                inp["quantity"] = _extract_quantity(user_input)
        return [{"step": 1, "agent": "CartAgent", "input": inp}]

    if intent == Intent.REC:
        return [{"step": 1, "agent": "RecommendAgent",
                 "input": {"user_input": user_input, "mcp": mcp}}]

    if intent == Intent.WEATHER:
        loc = _extract_location(user_input) or "Kathmandu"
        return [{"step": 1, "agent": "WeatherAgent", "input": {"location": loc, "mcp": mcp}}]

    if intent == Intent.TRYON:
        # TryOn is now a specialist agent (direct REST API via button).
        # If user types "try on X" in chat, guide them to use the Try On button.
        return []  # returns chitchat — handled by LLM fallback

    if intent == Intent.OWNER:
        action, params = _infer_owner_action(user_input)
        return [{"step": 1, "agent": "OwnerAgent",
                 "input": {"action": action, "params": params, "mcp": mcp}}]

    if intent == Intent.CHITCHAT:
        return []

    return [{"step": 1, "agent": "SearchAgent",
             "input": {"query": user_input, "filters": None, "mcp": mcp}}]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _infer_cart_action(text: str) -> str:
    t = text.lower()
    if any(k in t for k in [" to cart", " to basket", " into cart"]):
        return "add"
    if any(k in t for k in ["add", "put", "include", "buy"]):
        return "add"
    if any(k in t for k in ["remove", "delete", "drop"]):
        return "remove"
    if any(k in t for k in ["update", "change quantity", "set quantity"]):
        return "update"
    if any(k in t for k in ["clear", "empty"]):
        return "clear"
    return "view"


def _extract_product_name(text: str) -> str | None:
    patterns = [
        r"(?:add|buy|put)\s+(?:a\s+)?(?:few\s+)?(\d+)?\s*(.+?)(?:\s+to|\s+in|\s+cart|$)",
        r"(?:the\s+)?(.+?)\s+(?:tshirt|t-shirt|shirt|saree|sari|dress|jacket|jeans|kurti)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = (m.group(2) if m.lastindex >= 2 else m.group(1) or "").strip().strip("'\"")
            if name:
                return name.title()
    return None


def _extract_quantity(text: str) -> int:
    m = re.search(r"(\d+)\s*(?:x\s*|times?)?", text, re.IGNORECASE)
    return min(int(m.group(1)), 10) if m else 1


def _extract_location(text: str) -> str | None:
    for pat in [r"(?:in|at|near|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r"weather\s+(?:in|at)?\s*([A-Z][a-z]+)"]:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def _infer_owner_action(text: str) -> tuple[str, dict]:
    t = text.lower()
    if any(k in t for k in ["analytics", "revenue", "sales"]):
        return "analytics", {}
    if "post" in t and ("facebook" in t or "social" in t):
        return "post_facebook", {}
    if any(k in t for k in ["add product", "new product"]):
        return "add_product", {}
    return "inventory", {}
