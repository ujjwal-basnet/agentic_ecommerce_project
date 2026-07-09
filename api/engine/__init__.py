"""Engine — 4-stage pipeline orchestrator.

Flow: planner (LLM, extracts params) → binder (pure Python) →
      substitution (passthrough) → executor (DAG runner) → build_output.

No Redis. No per-step LLM calls. Typical chat turn does ONE LLM call
(planner) plus whatever tool calls the agents make.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from api import db as database
from api.agents import get_agent_registry
from api.config import PROTOCOL_LOG_PATH
from api.engine.binder import BindingError, bind_plan
from api.engine.executor_v2 import PipelineExecutor
from api.engine.planner_v2 import create_plan
from api.engine.response import generate_response_text
from api.engine.schemas import CapabilityPlan, CapabilityStep, ResolvedPlan, StepStatus
from api.guardrails import filter_model_output, sanitize_user_input

logger = logging.getLogger(__name__)


# ── Protocol logging ─────────────────────────────────────────────────────────


def _log(event: str, **kwargs):
    record = {"event": event, "ts": datetime.now().isoformat(), **kwargs}
    logger.info("protocol.%s %s", event, kwargs)

    async def _write():
        try:
            def _do():
                p = Path(PROTOCOL_LOG_PATH)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
            await asyncio.to_thread(_do)
        except Exception:
            logger.debug("protocol log write failed", exc_info=True)

    try:
        asyncio.get_running_loop().create_task(_write())
    except RuntimeError:
        pass


_CART_WORDS = frozenset({"cart", "remove", "delete", "checkout", "clear", "order"})
_ADD_TO_CART_RE = re.compile(
    r"^\s*(?:please\s+)?(?:add|put|throw)\b.*?\b(?:to|in(?:to)?)\s+(?:my\s+)?cart\b"
    r"|^\s*(?:add|put)\b.*?\b(?:cart)\b",
    re.IGNORECASE,
)
_GREETING_ONLY_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|yo+|namaste|namaskar)"
    r"(?:\s+(?:bot|smartshop|assistant|there))?\s*[!.?]*\s*$",
    re.IGNORECASE,
)
_ACK_ONLY_RE = re.compile(
    r"^\s*((?:great|wow|nice|cool|awesome|perfect|ok|okay|thanks|thank you|"
    r"thx|good|sounds good|lol|haha|hehe|yay|yep|yes|sure|alright|got it|noted)"
    r"[!.?\s]*)+(\s*[!.?])?\s*$",
    re.IGNORECASE,
)
_AMBIGUOUS_ONLY_RE = re.compile(
    r"^\s*(what|what\?|huh|wait|sorry what|what do you mean)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_HOW_ARE_YOU_RE = re.compile(
    r"^\s*(?:how\s+(?:are|r)\s+(?:you|u)|how\s+(?:are\s+)?(?:you|u)\s+doing|"
    r"how'?s\s+(?:it|everything)\s+going)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_PRICE_MAX_RE = re.compile(
    r"\b(?:under|below|less\s+than|cheaper\s+than|within|up\s+to|"
    r"max(?:imum)?|budget(?:\s+of)?)\s*(?:rs\.?|nrs|₹)?\s*([\d,]+)"
    r"\s*(?:rs\.?|nrs|rupees?)?\b"
    r"|(?:rs\.?|nrs|₹)?\s*([\d,]+)\s*(?:rs\.?|nrs|rupees?)?"
    r"\s*(?:or\s+)?(?:under|below|less|max(?:imum)?|budget)\b",
    re.IGNORECASE,
)
_PRICE_REFERENCE_RE = re.compile(
    r"\b(price|cost|how\s+much|rate)\b.*\b(this|it|that|one|product)\b"
    r"|\b(this|it|that|one|product)\b.*\b(price|cost|how\s+much|rate)\b",
    re.IGNORECASE,
)
_DRINK_REFERENCE_RE = re.compile(
    r"\b(can|could|should)\s+i\s+drink\s+(this|it|that|one)\b"
    r"|\bis\s+(this|it|that|one)\s+(drinkable|a\s+drink|a\s+beverage)\b",
    re.IGNORECASE,
)
def _parse_catalog_products() -> list[dict]:
    """Parse all products from data/products.md into structured dicts."""
    path = Path("data/products.md")
    if not path.exists():
        return []
    products = []
    pattern = re.compile(
        r"-\s+id=(\d+)\s+·\s+(.+?)\s+·\s+Rs\.\s*([\d,]+)\s+·\s+color:\s*([^·]+?)\s+·\s+tags:\s*(\[.+?\])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        try:
            products.append({
                "id": int(match.group(1)),
                "name": match.group(2).strip(),
                "price": int(match.group(3).replace(",", "")),
                "color": match.group(4).strip(),
                "tags": match.group(5).strip(),
            })
        except (ValueError, IndexError):
            continue
    return products


def _resolve_products_plan(
    user_input: str,
    product_ids: list[int],
    strategy: str,
) -> CapabilityPlan:
    return CapabilityPlan(
        user_request=user_input,
        overall_strategy=strategy,
        steps=[
            CapabilityStep(
                step_id="s1",
                capability="resolve_products",
                description=strategy,
                parameters={"product_ids": product_ids},
            )
        ],
    )


def _extract_max_price(user_input: str) -> int | None:
    match = _PRICE_MAX_RE.search(user_input)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    if not raw:
        return None
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        return None


def _format_rs(amount: int | float) -> str:
    return f"Rs. {int(amount):,}"


def _last_mentioned_product_ids(session_id: str, limit: int = 8) -> list[int]:
    """Find product IDs mentioned in recent assistant messages."""
    products = _parse_catalog_products()
    if not products:
        return []

    rows = database.load_history(session_id, limit=limit)
    for msg in reversed(rows):
        if msg.get("role") != "assistant":
            continue
        content = (msg.get("content") or "").lower()
        if not content:
            continue
        matched: list[int] = []
        for product in products:
            name = str(product.get("name") or "").lower()
            if name and name in content:
                matched.append(int(product["id"]))
        if matched:
            return matched
    return []


def _deterministic_reference_plan(
    user_input: str,
    session_id: str,
) -> CapabilityPlan | None:
    if not (_PRICE_REFERENCE_RE.search(user_input) or _DRINK_REFERENCE_RE.search(user_input)):
        return None
    ids = _last_mentioned_product_ids(session_id)
    if not ids:
        return None
    return _resolve_products_plan(
        user_input,
        ids,
        "Deterministic referenced product question",
    )


def _deterministic_budget_plan(user_input: str) -> CapabilityPlan | None:
    """Standalone budget guard: 'under 500' → exact price<=N from the catalog.

    Exact numeric filtering stays deterministic because LLMs miscompare numbers.
    Any other constraints in the same query (color/category) are then enforced by
    the constraint validator on the resolved products.
    """
    max_price = _extract_max_price(user_input)
    if max_price is None:
        return None

    products = _parse_catalog_products()
    if not products:
        return None

    matches = [p for p in products if p["price"] <= max_price]
    if matches:
        ids = [p["id"] for p in matches]
        return _resolve_products_plan(
            user_input,
            ids,
            f"Deterministic budget match under {_format_rs(max_price)}",
        )

    lowest = min(products, key=lambda p: p["price"])
    return CapabilityPlan(
        user_request=user_input,
        overall_strategy="Deterministic budget no-match",
        direct_response=(
            f"I don't have any products under {_format_rs(max_price)} right now. "
            f"The lowest priced option is {lowest['name']} at {_format_rs(lowest['price'])}."
        ),
    )


def _fuzzy_match_product(query: str, products: list[dict]) -> dict | None:
    """Find the best matching product using token overlap (Jaccard similarity).

    Handles typos and alternate spellings by comparing word sets.
    Returns the best-matching product dict or None if no good match found.
    """
    # Strip common cart-action words from the query before matching
    stop = {"add", "put", "to", "my", "cart", "the", "a", "an", "please",
            "into", "in", "throw", "for", "me", "i", "want"}
    query_tokens = set(
        w for w in re.sub(r"[^a-z0-9 ]", " ", query.lower()).split()
        if w not in stop and len(w) > 1
    )
    if not query_tokens:
        return None

    best_product = None
    best_score = 0.0

    for product in products:
        name_tokens = set(
            w for w in re.sub(r"[^a-z0-9 ]", " ", product["name"].lower()).split()
            if len(w) > 1
        )
        # Jaccard similarity = intersection / union
        intersection = query_tokens & name_tokens
        union = query_tokens | name_tokens
        score = len(intersection) / len(union) if union else 0.0

        if score > best_score:
            best_score = score
            best_product = product

    # Require at least 25% token overlap to avoid false matches
    return best_product if best_score >= 0.25 else None


def _deterministic_add_to_cart_plan(user_input: str) -> CapabilityPlan | None:
    """Fast-path for 'add <product name> to cart' without an LLM call.

    Fuzzy-matches the product name from the catalog so typos like
    'harry potter' → 'Harry Porter' still resolve correctly.
    """
    if not _ADD_TO_CART_RE.match(user_input):
        return None

    products = _parse_catalog_products()
    if not products:
        return None

    matched = _fuzzy_match_product(user_input, products)
    if not matched:
        return None

    logger.info(
        "deterministic_add_to_cart: matched id=%d name=%r for query=%r",
        matched["id"], matched["name"], user_input,
    )
    return CapabilityPlan(
        user_request=user_input,
        overall_strategy=f"Deterministic add-to-cart: fuzzy matched '{matched['name']}'",
        steps=[
            CapabilityStep(
                step_id="s1",
                capability="add_to_cart",
                description=f"Add '{matched['name']}' to cart",
                parameters={
                    "product_id": matched["id"],
                    "product_name": matched["name"],
                    "quantity": 1,
                },
            )
        ],
    )



# ── Constraint validator (post-check on planner output) ───────────────────────
#
# The planner *selects* products by reasoning over the catalog; this validator
# guarantees the selection actually matches the constraints the user stated, so a
# wrong-attribute item (e.g. a red dumbbell for "red shirt") can never reach the
# customer. It ONLY filters — it never adds or invents products.

# Stated color -> tokens accepted in a product's `color` field (royal counts as blue).
_COLOR_SYNONYMS: dict[str, set[str]] = {
    "red": {"red"},
    "blue": {"blue", "royal", "navy"},
    "royal": {"royal", "blue"},
    "black": {"black"},
    "green": {"green"},
    "white": {"white"},
    "silver": {"silver", "grey", "gray"},
    "grey": {"grey", "gray", "silver"},
    "gray": {"grey", "gray", "silver"},
    "cream": {"cream"},
}

# Requested category keyword -> acceptable product `category` values (DB labels).
_CATEGORY_LABELS: dict[str, set[str]] = {
    "shirt": {"shirt"}, "tshirt": {"shirt"}, "tee": {"shirt"}, "top": {"shirt"},
    "kurti": {"kurti"}, "suit": {"kurti"},
    "jeans": {"jeans"}, "denim": {"jeans"},
    "jacket": {"jacket"}, "fleece": {"jacket"},
    "laptop": {"laptops"}, "notebook": {"laptops"},
    "sunglasses": {"accessories"}, "glasses": {"accessories"},
    "keyboard": {"general"},
    "drink": {"drink", "general"}, "beverage": {"drink", "general"}, "soda": {"drink", "general"},
    "snack": {"snack"}, "chips": {"snack"},
    "dumbbell": {"fitness"}, "barbell": {"fitness"},
    "food": {"snack", "drink"}, "hungry": {"snack", "drink"}, "eat": {"snack"}, "thirsty": {"drink"},
    # "electronics" is a coarse label shared by several items — disambiguate by name.
    "speaker": {"electronics"}, "camera": {"electronics"}, "cctv": {"electronics"},
    "charger": {"electronics"}, "adapter": {"electronics"}, "fan": {"electronics"},
}
# Electronics keywords also require a name/description hit so "speaker" doesn't
# match a camera that merely shares the "electronics" category.
_CATEGORY_NAME_HINTS: dict[str, set[str]] = {
    "speaker": {"speaker", "soundbox", "bluetooth"},
    "camera": {"camera", "cctv"},
    "cctv": {"camera", "cctv"},
    "charger": {"charger", "adapter", "power adapter", "usb-c", "cable"},
    "adapter": {"charger", "adapter", "power adapter"},
    "fan": {"fan"},
    "drink": {"sprite", "cola", "coke", "soda", "drink", "beverage", "juice", "water", "lemon", "lime"},
    "beverage": {"sprite", "cola", "coke", "soda", "drink", "beverage", "juice", "water", "lemon", "lime"},
    "soda": {"sprite", "cola", "coke", "soda"},
    "food": {"pringles", "chips", "sprite", "lemon", "lime", "drink", "beverage", "soda", "snack"},
    "hungry": {"pringles", "chips", "sprite", "lemon", "lime", "drink", "beverage", "soda", "snack"},
    "eat": {"pringles", "chips", "snack"},
    "thirsty": {"sprite", "cola", "coke", "soda", "drink", "beverage", "juice", "water", "lemon", "lime"},
}
_CATEGORY_KEYS = list(_CATEGORY_LABELS.keys())
_CATEGORY_FUZZY_KEYS = [k for k in _CATEGORY_KEYS if len(k) >= 5]


def _stated_color(user_input: str) -> str | None:
    """Return the first non-negated color mentioned by the user.

    Handles compound negation like 'not white or black' by also skipping
    colors joined with 'or'/'and' after a negation trigger.
    """
    text = user_input.lower()
    negated = set(_extract_negated_words(text))
    for color in _COLOR_SYNONYMS:
        if not re.search(rf"\b{re.escape(color)}\b", text):
            continue
        if color in negated:
            continue
        # Also skip if directly preceded by a negation keyword
        idx = text.find(color)
        if idx > 0:
            preceding = text[max(0, idx - 15):idx]
            if any(neg in preceding for neg in ["not", "except", "excluding", "no", "other than", "without"]):
                continue
        return color
    return None


def _requested_category(user_input: str) -> str | None:
    text = user_input.lower()
    for kw in _CATEGORY_KEYS:  # exact word match first
        if re.search(rf"\b{re.escape(kw)}\b", text):
            # Ignore if negated (e.g., "not laptops")
            idx = text.find(kw)
            if idx > 0:
                preceding = text[max(0, idx-15):idx]
                if any(neg in preceding for neg in ["not", "except", "excluding", "no", "other than", "without"]):
                    continue
            return kw
    for tok in re.findall(r"[a-z]{5,}", text):  # typo tolerance ("thisrt" -> tshirt)
        match = difflib.get_close_matches(tok, _CATEGORY_FUZZY_KEYS, n=1, cutoff=0.8)
        if match:
            # Ignore if negated
            kw = match[0]
            idx = text.find(tok)
            if idx > 0:
                preceding = text[max(0, idx-15):idx]
                if any(neg in preceding for neg in ["not", "except", "excluding", "no", "other than", "without"]):
                    continue
            return kw
    return None


def _color_matches(stated: str, product: dict) -> bool:
    prod_color = str(product.get("color") or "").lower()
    return any(tok in prod_color for tok in _COLOR_SYNONYMS.get(stated, {stated}))


def _category_matches(kw: str, product: dict) -> bool:
    prod_cat = str(product.get("category") or "").lower()
    if prod_cat not in _CATEGORY_LABELS.get(kw, set()):
        return False
    hints = _CATEGORY_NAME_HINTS.get(kw)
    if hints:
        hay = f"{product.get('name') or ''} {product.get('description') or ''}".lower()
        return any(h in hay for h in hints)
    return True


def _extract_negated_words(user_input: str) -> list[str]:
    text = user_input.lower()
    _SKIP_WORDS = frozenset({
        "a", "the", "an", "some", "any",
        "laptop", "laptops", "shirt", "shirts", "speaker", "speakers",
        "one", "ones", "colored", "color",
    })
    # Expand common contractions so "aren't white" → "are not white"
    _CONTRACTIONS = {
        "aren't": "are not",
        "isn't": "is not",
        "don't": "do not",
        "doesn't": "does not",
        "won't": "will not",
        "can't": "can not",
        "wouldn't": "would not",
        "shouldn't": "should not",
    }
    for contraction, expansion in _CONTRACTIONS.items():
        text = text.replace(contraction, expansion)
    # Handle compound negation: "not X or Y", "not X and Y"
    # e.g. "not white or black" → negate both white and black
    compound_neg_re = re.compile(
        r"\b(?:not|except|excluding|other\s+than|without)\s+([a-z0-9\-]+)"
        r"(?:\s+(?:or|and|nor)\s+([a-z0-9\-]+))*",
        re.IGNORECASE,
    )
    negated = []
    for m in compound_neg_re.finditer(text):
        full = m.group(0)
        # Skip the first word (negation trigger), extract remaining words
        rest = full.split(None, 1)[1] if len(full.split()) > 1 else ""
        words = re.findall(r"[a-z0-9\-]+", rest)
        for w in words:
            if w not in ("or", "and", "nor") and w not in _SKIP_WORDS:
                negated.append(w)
    # Also match standalone "without X"
    for w in re.findall(r"\bwithout\s+([a-z0-9\-]+)", text):
        if w not in _SKIP_WORDS and w not in negated:
            negated.append(w)
    return negated




def _split_bundled_queries(user_input: str) -> list[str]:
    """Split compound action queries into individual sub-queries.

    Handles: "add X and then show Y", "find X and also add Y", "add X and Y",
             "my phone is dead, add a charger and also get chips".
    """
    cleaned = user_input.strip()

    # ── Strategy 1: explicit action-verb boundary after "and/then/also" ───────
    # Split on: " and then ", " and also ", " then ", " and " when followed
    # by an action verb or a digit or quantity word.
    action_verbs = r"(?:add|show|find|get|buy|checkout|put|remove|delete|clear|try\s+on|want\s+to\s+try)"
    qty_words = r"(?:\d+|some|a|the|another|one)"

    split_re = re.compile(
        r"\s+(?:and\s+(?:then|also)\s+|then\s+|and\s+)(?="
        + action_verbs + r"|\d+\s+" + r"|" + qty_words + r"\s+)",
        re.IGNORECASE,
    )

    # Guard: do not split if the query refers to a known compound product name
    _PROTECTED_PHRASES = (
        "sour cream and onion",
        "lemon and lime",
        "salt and pepper",
        "mac and cheese",
        "black and white",
    )
    cleaned_lower_check = cleaned.lower()
    for phrase in _PROTECTED_PHRASES:
        if phrase in cleaned_lower_check:
            # Only block if no separate action verb follows the phrase
            after = cleaned_lower_check[cleaned_lower_check.find(phrase) + len(phrase):]
            if not re.search(r"\b(?:and\s+(?:then|also)\s+|then\s+)(?:add|show|find|get)", after, re.IGNORECASE):
                return [cleaned]

    parts = split_re.split(cleaned)
    # Use regex to cleanly strip trailing whitespace/punctuation but NOT letters
    parts = [re.sub(r"[\s,;]+$", "", p).strip() for p in parts if p.strip()]

    if len(parts) > 1:
        # Determine the action implied by the first sub-query so we can
        # prepend it to any later sub-query that lacks its own verb.
        first_lower = parts[0].lower()
        implied_verb = ""
        for verb in ("show", "find", "get", "add", "remove", "buy", "checkout"):
            if re.search(rf"\b{verb}\b", first_lower):
                implied_verb = verb + " "
                break

        result = [parts[0]]
        for part in parts[1:]:
            p_lower = part.lower()
            # Only prepend if this sub-query has no leading action verb
            has_verb = any(
                re.match(rf"\b{v}\b", p_lower)
                for v in ("add", "show", "find", "get", "buy", "checkout", "remove", "put")
            )
            if not has_verb and implied_verb:
                part = implied_verb + part
            result.append(part)
        return result

    # ── Strategy 2: "add X and Y" where Y is a bare product name ─────────────
    if re.search(r"\badd\b", cleaned, re.IGNORECASE) and " and " in cleaned.lower():
        # Find the last " and " that is NOT part of a product name like
        # "Sour Cream and Onion" or "Lemon and Lime".
        _PRODUCT_NAME_ANDS = {
            ("sour cream", "onion"),
            ("lemon", "lime"),
            ("salt", "pepper"),
            ("cream", "cheese"),
        }
        and_idx = cleaned.lower().rfind(" and ")
        if and_idx > 0:
            part1 = cleaned[:and_idx].strip()
            part2 = cleaned[and_idx + 5:].strip()
            pair = (part1.split()[-1].lower() if part1.split() else "", part2.split()[0].lower() if part2.split() else "")
            if pair not in _PRODUCT_NAME_ANDS and part2:
                return [part1, "add " + part2]


    return [cleaned]



def _enforce_constraints(
    user_input: str, products: list[dict]
) -> tuple[list[dict], bool]:
    """Drop products that don't match the color/category/price/negation the user stated.

    Returns (kept, constrained). `constrained` is True when the user stated at
    least one constraint, so the caller can show an honest no-match message if
    everything was filtered out. Never adds products.
    """
    if not products:
        return products, False

    color = _stated_color(user_input)
    category = _requested_category(user_input)
    max_price = _extract_max_price(user_input)
    negated = _extract_negated_words(user_input)
    
    if not (color or category or max_price is not None or negated):
        return products, False

    kept: list[dict] = []
    for p in products:
        if color and not _color_matches(color, p):
            continue
        if category and not _category_matches(category, p):
            continue
        if max_price is not None:
            try:
                if float(p.get("price") or 0) > max_price:
                    continue
            except (TypeError, ValueError):
                continue
        # Negation constraint
        if negated:
            name_desc_tags = f"{p.get('name') or ''} {p.get('description') or ''} {' '.join(p.get('tags') or [])}".lower()
            if any(word in name_desc_tags for word in negated):
                continue
        kept.append(p)
    return kept, True



def _normalize_user_input(text: str) -> str:
    """Fix common no-space typos before intent routing."""
    cleaned = text or ""
    cleaned = re.sub(
        r"\b(anything|something|gift)(for)\b",
        r"\1 \2",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _direct_chat_response(user_input: str) -> str | None:
    """Fast path for turns that should never show product cards."""
    q = user_input.strip().lower()
    
    # 1. Greetings
    if _GREETING_ONLY_RE.match(user_input) or q in ("hi", "hello", "hey", "namaste", "ke xa"):
        return "Hi! What can I help you find today?"
        
    # 2. How are you / smalltalk
    if any(phrase in q for phrase in ["how are you", "how r u", "how you doing", "how is it going", "how's it going", "how is everything", "how are you today"]):
        return "I'm doing great, thank you! What can I help you find today?"
        
    # 3. Affection / Compliments
    if any(phrase in q for phrase in ["love you", "love u", "i love", "you are great", "you are awesome"]):
        return "Aww, thank you! I'm here to help you shop. What can I find for you today?"
        
    # 4. Acknowledgement
    if _ACK_ONLY_RE.match(user_input) or q in ("thanks", "thank you", "ok", "okay", "cool"):
        return "Glad you liked it. Want me to find another option or add it to your cart?"
        
    # 5. Ambiguity
    if _AMBIGUOUS_ONLY_RE.match(user_input):
        return "Which part should I clarify?"
        
    return None



# ── History helpers ───────────────────────────────────────────────────────────


def _get_history_context(session_id: str, limit: int = 6) -> str:
    """Build conversation context for the planner.

    Keeps user messages fuller (captures intent, gender, preferences).
    Truncates assistant responses (just need the gist of what was shown).
    """
    rows = database.load_history(session_id, limit=limit)
    if not rows:
        return ""
    lines = []
    for msg in rows:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        max_len = 200 if role == "User" else 150
        if len(content) > max_len:
            content = content[:max_len].rsplit(" ", 1)[0] + "…"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)



def _save_messages_async(
    session_id: str, user_input: str, assistant_text: str | None
) -> None:
    """Save user + assistant messages to chat history (synchronous).

    We deliberately save synchronously (not fire-and-forget) so that the
    next turn always sees the latest history. The DB INSERT takes <1ms
    so the latency impact is negligible, and it prevents a race condition
    where fast consecutive turns see stale/empty history.
    """
    try:
        database.save_message(session_id, "user", user_input)
        if assistant_text:
            database.save_message(session_id, "assistant", assistant_text)
    except Exception:
        logger.exception("save_message failed session=%s", session_id)



def _build_context(
    context: str,
    history: str,
    user_image_path: str | None,
    user_input: str,
) -> str:
    """Compose the non-catalog context sent to the planner.

    The catalog is injected directly into the planner's system prompt — we
    don't duplicate it here. We also always ask the LLM to reply in English
    regardless of user's input language; that keeps the responses consistent
    and avoids a second LLM round-trip for translation.
    """
    parts: list[str] = []
    if context:
        parts.append(context)
    if history:
        parts.append(f"Recent conversation:\n{history}")
    if user_image_path:
        parts.append(f"User uploaded photo: {user_image_path}")
    return "\n".join(parts)


def _sanitize_text(text: str) -> str:
    cleaned = (text or "").replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s{0,3}[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s{0,3}\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _build_direct_response(
    text: str,
    session_id: str,
) -> dict:
    cleaned = _sanitize_text(text)
    filtered = filter_model_output(cleaned)
    if filtered.flagged:
        _log("output_flagged", session_id=session_id, matches=filtered.matches)
    return {
        "text": filtered.text,
        "component": None,
        "cart_count": database.cart_count(session_id),
        "data": {},
        "products": None,
        "images": None,
        "session_id": session_id,
    }


async def _attach_meme_image(output: dict, user_input: str, channel: str) -> None:
    """Attach a Pinecone-selected meme reaction image for web chat turns."""
    if channel != "web":
        return
    if output.get("component") or output.get("products"):
        return
    try:
        from api.rag.meme_store import select_meme_for_turn

        meme = await select_meme_for_turn(user_input, output.get("text") or "")
    except Exception as e:
        logger.warning("Meme RAG selection failed: %s", e)
        return

    image_path = (meme or {}).get("image_path")
    if not image_path:
        return

    images = list(output.get("images") or [])
    if image_path not in images:
        images.append(image_path)
    output["images"] = images
    if isinstance(output.get("data"), dict):
        output["data"]["meme"] = meme


def _inject_context(
    plan: ResolvedPlan,
    session_id: str,
    user_image_path: str | None,
) -> None:
    """Inject session_id + user_image_path into step parameters where needed."""
    registry = get_agent_registry()
    for step in plan.steps:
        try:
            card = registry.get_by_name(step.agent_name)
        except KeyError:
            continue
        schema = card.input_schema or {}
        if "session_id" in schema:
            step.parameters["session_id"] = session_id
        if "user_image_path" in schema and user_image_path:
            step.parameters["user_image_path"] = user_image_path

        # For cart agent, derive the `action` from the capability if missing
        if step.agent_name == "CartAgent" and "action" not in step.parameters:
            action_map = {
                "add_to_cart": "add",
                "remove_from_cart": "remove",
                "view_cart": "view",
                "clear_cart": "clear",
            }
            step.parameters["action"] = action_map.get(step.capability, "view")


# ── Output building ───────────────────────────────────────────────────────────

_PRODUCT_AGENTS = {
    "ProductSearchAgent",
    "RecommendationAgent",
    "ResolveProductsAgent",
}


def _build_output(
    plan: ResolvedPlan,
    channel: str,
    session_id: str,
) -> dict:
    registry = get_agent_registry()
    output: dict[str, Any] = {
        "text": "",
        "component": None,
        "cart_count": database.cart_count(session_id),
        "data": {},
        "products": None,
        "images": None,
        "session_id": session_id,
    }

    all_products: list[dict] = []
    all_images: list[str] = []
    chosen_component: str | None = None

    for step in plan.steps:
        if step.status != StepStatus.DONE or step.result is None:
            continue

        result = step.result
        result_component = (
            result.get("component") if isinstance(result, dict) else None
        )

        if step.agent_name in _PRODUCT_AGENTS and isinstance(result, dict):
            prods = result.get("products") or []
            if prods:
                all_products.extend(prods)
                if channel == "web" and not chosen_component:
                    if result_component:
                        chosen_component = result_component
                    else:
                        try:
                            card = registry.get_by_name(step.agent_name)
                            if card.component:
                                chosen_component = card.component
                        except KeyError:
                            pass
            output["data"] = result
        elif step.agent_name == "TryOnAgent" and isinstance(result, dict):
            img = result.get("image_path")
            if img:
                all_images.append(img)
            output["data"] = result
        elif isinstance(result, dict):
            if channel == "web" and not chosen_component:
                if result_component:
                    chosen_component = result_component
                else:
                    try:
                        card = registry.get_by_name(step.agent_name)
                        if card.component:
                            chosen_component = card.component
                    except KeyError:
                        pass
            output["data"] = result

    if all_products:
        # Deduplicate by product id — keep first occurrence (preserves order)
        seen_ids: set = set()
        unique_products: list[dict] = []
        for p in all_products:
            pid = p.get("id")
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_products.append(p)
        output["products"] = unique_products
    if all_images:
        output["images"] = all_images
    if chosen_component:
        output["component"] = chosen_component

    output["cart_count"] = database.cart_count(session_id)
    # Text is filled in asynchronously by the caller — see `run()`.
    return output


# ── Main entry point ──────────────────────────────────────────────────────────


async def run(
    user_input: str,
    channel: str = "web",
    session_id: str | None = None,
    context: str = "",
    user_image_path: str | None = None,
) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    database.ensure_session(session_id)

    try:
        _log("user_input", session_id=session_id, message=user_input, channel=channel)

        if not user_input or not user_input.strip():
            return {
                "text": "How can I help you today?",
                "component": None,
                "cart_count": database.cart_count(session_id),
                "data": {},
                "products": None,
                "images": None,
                "session_id": session_id,
            }

        sanitized = sanitize_user_input(user_input)
        if sanitized.flagged:
            _log("input_flagged", session_id=session_id, matches=sanitized.matches)
        user_input = _normalize_user_input(sanitized.cleaned or user_input)

        turn_start = time.perf_counter()
        timings: dict[str, int] = {}

        def _ms(t0: float) -> int:
            return int((time.perf_counter() - t0) * 1000)

        direct_text = _direct_chat_response(user_input)
        if direct_text:
            output = _build_direct_response(direct_text, session_id)
            await _attach_meme_image(output, user_input, channel)
            _save_messages_async(session_id, user_input, output.get("text"))
            _log(
                "response",
                session_id=session_id,
                text=(output.get("text") or "")[:200],
                steps=0,
                direct="deterministic_chat",
            )
            return output

        # ── Planner-first routing ─────────────────────────────────────────────
        # No separate chitchat classifier. The planner reads the catalog, so IT
        # decides product-vs-smalltalk (it returns direct_response for chitchat).
        # A blind pre-classifier can't see the catalog and used to misroute real
        # product questions like "i think you have a drink its sprite?" into
        # chitchat. Only fast regex greetings (handled above) and the exact/
        # high-risk deterministic guards below skip the planner.
        deterministic_plan = (
            _deterministic_add_to_cart_plan(user_input)
            or _deterministic_reference_plan(user_input, session_id)
            or _deterministic_budget_plan(user_input)
        )

        history = _get_history_context(session_id, limit=6)
        rewritten = user_input

        full_context = _build_context(context, history, user_image_path, user_input)

        # Inject current cart contents ONLY if the user's message is cart-related
        if _CART_WORDS & set(user_input.lower().split()):
            cart_items = database.db_get_cart(session_id)
            if cart_items:
                cart_lines = [
                    f"- id={item.get('product_id')} | {item.get('product_name')} | "
                    f"color:{item.get('color', '')} | qty:{item.get('quantity')}"
                    for item in cart_items
                ]
                full_context += (
                    "\n\nCurrent cart contents:\n" + "\n".join(cart_lines)
                )

        # Stage 1: Planner (ONE LLM call — extracts both capabilities + parameters)
        # Feed rewritten query so planner sees explicit intent
        t = time.perf_counter()
        if not deterministic_plan:
            sub_queries = _split_bundled_queries(rewritten)
            if len(sub_queries) > 1:
                logger.info("Splitting bundled query: %r -> %r", rewritten, sub_queries)
                combined_steps = []
                strategies = []
                direct_responses = []
                for sq in sub_queries:
                    sub_plan = await create_plan(sq, full_context)
                    if sub_plan.steps:
                        for step in sub_plan.steps:
                            step_id = f"s{len(combined_steps) + 1}"
                            step.step_id = step_id
                            combined_steps.append(step)
                    if sub_plan.overall_strategy:
                        strategies.append(sub_plan.overall_strategy)
                    if sub_plan.direct_response:
                        direct_responses.append(sub_plan.direct_response)
                
                plan = CapabilityPlan(
                    plan_id=str(uuid.uuid4()),
                    user_request=user_input,
                    steps=combined_steps,
                    overall_strategy="Combined plan: " + " | ".join(strategies),
                    direct_response=" ".join(direct_responses) if direct_responses else None
                )
            else:
                plan = await create_plan(rewritten, full_context)
        else:
            plan = deterministic_plan
        timings["planner_ms"] = _ms(t)


        # If the planner emitted both steps AND a direct_response, prefer the
        # steps (the LLM sometimes pre-fills placeholder text we'd rather
        # generate from real results).
        if plan.direct_response and plan.steps:
            logger.info(
                "planner: discarding direct_response because plan has %d steps",
                len(plan.steps),
            )
            plan.direct_response = None

        # Empty plan with no reply = the planner treated this as chitchat (no
        # product intent) but didn't fill a message. Answer in a friendly way
        # instead of surfacing an error.
        if not plan.steps and not plan.direct_response:
            plan.direct_response = "Hey! What can I help you find today?"

        # Short-circuit: direct response
        if plan.direct_response:
            output = _build_direct_response(plan.direct_response, session_id)
            await _attach_meme_image(output, user_input, channel)
            _save_messages_async(session_id, user_input, output.get("text"))
            timings["total_ms"] = _ms(turn_start)
            _log("response", session_id=session_id,
                 text=(output.get("text") or "")[:200], steps=0, **timings)
            return output

        _log("plan_created", session_id=session_id,
             strategy=plan.overall_strategy,
             steps=[{"cap": s.capability, "params": s.parameters} for s in plan.steps])

        # Stage 2: Binder (pure Python)
        registry = get_agent_registry()
        t = time.perf_counter()
        try:
            resolved_plan = bind_plan(plan, registry)
        except BindingError as e:
            logger.warning("Binding failed: %s", e)
            output = _build_direct_response(
                "I'm not sure how to handle that. Could you rephrase?",
                session_id,
            )
            _save_messages_async(session_id, user_input, output.get("text"))
            return output
        timings["binder_ms"] = _ms(t)
        
        _inject_context(resolved_plan, session_id, user_image_path)
        timings["substitution_ms"] = 0  # removed stage

        # Stage 4: Executor (parallel DAG)
        t = time.perf_counter()
        executor = PipelineExecutor(registry, max_attempts=2)
        completed_plan = await executor.run(resolved_plan)
        timings["executor_ms"] = _ms(t)

        output = _build_output(completed_plan, channel, session_id)

        # ── Constraint validation guard ───────────────────────────────────────
        # The planner picked the products; ensure they actually match the color /
        # category / price the user stated. Filter-only — a wrong-attribute item
        # (e.g. a red dumbbell for "red shirt") can never reach the customer.
        resolved_products = output.get("products") or []
        if resolved_products:
            kept, constrained = _enforce_constraints(user_input, resolved_products)
            if constrained and len(kept) != len(resolved_products):
                _log("constraint_filter", session_id=session_id,
                     before=len(resolved_products), after=len(kept))
            output["products"] = kept or None
            if not kept:
                # Stated a constraint but nothing matched — show nothing; the
                # response generator emits an honest no-match message.
                output["component"] = None
                output["images"] = None

        # Async text generation — runs LLM only for question-style queries.
        output["text"] = await generate_response_text(
            completed_plan,
            output.get("products") or [],
            user_input,
        )
        filtered = filter_model_output(output["text"])
        if filtered.flagged:
            _log("output_flagged", session_id=session_id, matches=filtered.matches)
        output["text"] = filtered.text
        await _attach_meme_image(output, user_input, channel)

        _save_messages_async(session_id, user_input, output.get("text"))

        timings["total_ms"] = _ms(turn_start)
        _log("response", session_id=session_id,
             text=(output.get("text") or "")[:200],
             component=output.get("component"),
             steps=len(plan.steps),
             **timings)
        return output

    except Exception as exc:
        _log("error", session_id=session_id, message=user_input, error=repr(exc))
        logger.exception("engine.run failed session=%s message=%r", session_id, user_input)
        raise


async def run_text(user_input: str, session_id: str | None = None) -> str:
    result = await run(user_input, channel="text", session_id=session_id)
    return result.get("text", "Sorry, something went wrong.")
