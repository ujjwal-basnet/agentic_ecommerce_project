"""Semantic Routing Layer.

Exposes a fast query routing engine using vLLM/OpenAI-compatible embeddings
and falls back to deterministic hash-based mock embeddings when the server is unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
import httpx
from functools import lru_cache
from typing import Literal, NamedTuple

from pydantic import BaseModel

from api import config

logger = logging.getLogger(__name__)

# ── Routes Definitions ────────────────────────────────────────────────────────

class Route(NamedTuple):
    name: str
    utterances: list[str]

ROUTES = [
    Route(
        name="chitchat",
        utterances=[
            # greetings
            "hi",
            "hello",
            "hey",
            "hey there",
            "good morning",
            "good afternoon",
            "yo",
            "namaste",
            "namaskar",
            "hello bot",
            "hi bot",
            "sup",
            # compliments / acks
            "thank you",
            "thanks",
            "wow",
            "that's awesome",
            "awesome",
            "great",
            "nice",
            "cool",
            "you are so cool",
            "perfect",
            "ok",
            "okay",
            "yep",
            "sure",
            "alright",
            "got it",
            "noted",
            # farewells
            "bye",
            "goodbye",
            "see you",
            "talk to you later",
            # general chat
            "how are you",
            "how r you",
            "how r u",
            "how are u",
            "how you doing",
            "how are things going",
            "who are you",
            "what is your name",
            "what can you do",
            "are you human",
            "tell me a joke",
            "how is the weather",
            "let's chat",
            "tell me something interesting",
            "sanchai hunuhunchha",
            "ke xa",
            "k xa",
            "ke chha",
            "timi ko hau",
        ],
    ),
    Route(
        name="cart_actions",
        utterances=[
            "view cart",
            "show my cart",
            "view my shopping cart",
            "what is in my cart",
            "checkout",
            "checkout my items",
            "place order",
            "complete purchase",
            "buy these items",
            "place my order",
            "clear cart",
            "clear my cart",
            "empty cart",
            "add to cart",
            "add this product to my cart",
            "add to cart harry potter shirt",
            "add this item to my cart",
            "remove this from cart",
            "delete from cart",
        ],
    ),
    Route(
        name="requires_history",
        utterances=[
            # Reference to a previously shown item — must be very specific
            "how about the first one",
            "cheaper ones",
            "cheaper one",
            "show me that one",
            "add it to cart",
            "remove it from cart",
            "yes please add it",
            "no thanks skip it",
            "do you have it in black color",
            "show more of those items",
            "what about this specific one",
            "the second one please",
            "the previous product",
            "same item but different color",
            "can I see it in blue",
        ],
    ),
    Route(
        name="search_products",
        utterances=[
            # Clothing & fashion
            "show me laptops",
            "find laptops",
            "laptops under 50000",
            "show me shirts",
            "red shirt for men",
            "blue shirt for women",
            "shirts for men",
            "t shirt",
            "kurtis",
            "show kurtis",
            "black shoes",
            "find shoes",
            "do you sell shirts",
            "show me clothes",
            # Food & grocery
            "anything to eat",
            "food items",
            "something to eat",
            "drinks",
            "snacks",
            "any snacks available",
            "grocery items",
            "beverages",
            # Electronics
            "wifi camera",
            "cctv camera",
            "security camera",
            "mechanical keyboard",
            "gaming keyboard",
            "wireless mouse",
            "bluetooth speaker",
            "headphones",
            "smartwatch",
            "mobile phone",
            # General
            "list all products",
            "show catalog",
            "browse products",
            "what do you sell",
        ],
    ),
]

# ── Embedding & Similarity Logic ──────────────────────────────────────────────

_USE_MOCK_EMBED: bool | None = None
_UTTERANCE_EMBEDDINGS: dict[str, list[list[float]]] = {}

STOP_WORDS = {
    "what", "is", "your", "me", "for", "the", "a", "an", "to", "in", "on", 
    "at", "by", "from", "with", "about", "as", "into", "like", "through", 
    "after", "before", "of", "and", "or", "but", "if", "then", "else", 
    "i", "you", "he", "she", "it", "we", "they", "my", "his", "her", "their",
    "our", "do", "does", "did", "can", "could", "would", "should", "will", "shall"
}

_COLOR_RE = r"(red|blue|royal|black|white|silver|grey|gray)"
_COLOR_REFINEMENT_RE = re.compile(
    rf"\b(?:in|same|that|this|one|ones|it)\b.*\b{_COLOR_RE}\b"
    rf"|\b{_COLOR_RE}\b\s+(?:one|ones|color)\b",
    re.IGNORECASE,
)

def _mock_embed(text: str, dim: int = 1024) -> list[float]:
    """Fallback deterministic token-based pseudo-embedding when vLLM/OpenAI is offline.
    
    Filters out common high-frequency grammar tokens to prevent misrouting due to structural overlaps.
    """
    words = text.lower().split()
    if not words:
        return [1.0 / math.sqrt(dim)] * dim

    vec = [0.0] * dim
    has_tokens = False
    for w in words:
        # Clean word from punctuation
        cleaned_w = "".join(c for c in w if c.isalnum())
        if not cleaned_w or cleaned_w in STOP_WORDS:
            continue
        h_val = int(hashlib.md5(cleaned_w.encode("utf-8")).hexdigest(), 16)
        idx = h_val % dim
        vec[idx] += 1.0
        has_tokens = True

    if not has_tokens:
        # If all words were stop words, fall back to hashing the original cleaned words
        for w in words:
            cleaned_w = "".join(c for c in w if c.isalnum())
            if not cleaned_w:
                continue
            h_val = int(hashlib.md5(cleaned_w.encode("utf-8")).hexdigest(), 16)
            idx = h_val % dim
            vec[idx] += 1.0

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity of two normalized vectors."""
    if len(a) != len(b) or not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


async def get_embedding_direct(text: str) -> list[float] | None:
    """Make raw POST request to vLLM/OpenAI embedding endpoint."""
    base_url = getattr(config, "EMBEDDING_BASE_URL", config.LLM_BASE_URL)
    if not base_url:
        return None

    # Handle standard path mapping (v1/embeddings or embeddings)
    base_url = base_url.rstrip("/")
    url = f"{base_url}/embeddings"

    # Match model name
    model_name = getattr(config, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    try:
        headers = {"Content-Type": "application/json"}
        if config.OPENAI_API_KEY:
            headers["Authorization"] = f"Bearer {config.OPENAI_API_KEY}"

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "input": text,
                    "model": model_name,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("data", [{}])[0].get("embedding")
                if emb:
                    return [float(x) for x in emb]
    except Exception as e:
        logger.debug("Failed to fetch embedding from %s: %s", url, e)
    return None


async def get_embedding(text: str) -> list[float]:
    """Retrieve embedding with automatic mock fallback."""
    global _USE_MOCK_EMBED
    if _USE_MOCK_EMBED is None:
        await init_router()

    if not _USE_MOCK_EMBED:
        emb = await get_embedding_direct(text)
        if emb:
            return emb
        # If transient failure, fall back to mock
    return _mock_embed(text)


async def init_router(force_reinit: bool = False) -> None:
    """Detect if embedding API is available and precompute route embeddings."""
    global _USE_MOCK_EMBED, _UTTERANCE_EMBEDDINGS
    if _USE_MOCK_EMBED is not None and not force_reinit:
        return

    # 1. Test embedding endpoint
    _USE_MOCK_EMBED = True
    base_url = getattr(config, "EMBEDDING_BASE_URL", config.LLM_BASE_URL)
    if base_url:
        try:
            emb = await get_embedding_direct("test")
            if emb:
                _USE_MOCK_EMBED = False
                logger.info("Semantic routing: initialized with real embedding endpoint.")
        except Exception:
            pass

    if _USE_MOCK_EMBED:
        logger.info("Semantic routing: falling back to mock hash-based embeddings.")

    # 2. Precompute utterance embeddings
    _UTTERANCE_EMBEDDINGS.clear()
    for route in ROUTES:
        embeddings = []
        for utterance in route.utterances:
            emb = await get_embedding(utterance)
            embeddings.append(emb)
        _UTTERANCE_EMBEDDINGS[route.name] = embeddings


# ── LLM Intent Classifier (primary router) ────────────────────────────────────
#
# Instead of matching a hand-maintained list of example utterances, we let the
# LLM read the message and name the intent. This generalizes to ANY phrasing —
# "how r u", "wassup", "u good?" all classify as chitchat with zero new rules.
# The embedding router below stays as an offline / failure fallback.

_INTENT_LABELS = ("chitchat", "cart_actions", "requires_history", "search_products", "others")

_INTENT_SYSTEM = """You are the intent router for SmartShop, a shopping assistant.
Classify the user's LATEST message into EXACTLY ONE intent. Output only the intent.

Intents:
- chitchat: greetings, small talk, feelings, thanks, jokes, "how are you" / "how r u" / "wassup" / "u good?", "who are you", "what can you do", or any casual line with no shopping goal. This applies EVEN IF earlier turns were about products.
- cart_actions: add / remove / view / clear the cart, checkout, place order, buy now.
- requires_history: refers to a previously shown item without naming it — "the first one", "cheaper one", "show it in black", "add that one", "same but blue".
- search_products: find / browse / recommend products, ask what's available, or ask about a product's price / category / color / stock.
- others: policy or FAQ questions (returns, shipping, sizing, warranty) and anything that fits none of the above.

Rules:
- Decide from the LATEST message. Do NOT let previous product turns drag small talk into search_products.
- If a line is clearly casual conversation, choose chitchat even when it is short or misspelled.
- Reply with only the intent label."""


class _IntentDecision(BaseModel):
    intent: Literal["chitchat", "cart_actions", "requires_history", "search_products", "others"]


@lru_cache(maxsize=1)
def _intent_agent():
    """Cached pydantic-ai agent that outputs a single intent label as plain text.

    We avoid NativeOutput / response_format here because small local models
    (Qwen3 via vLLM) sometimes return empty content when a JSON schema is
    enforced, causing pydantic-ai to raise "model output must contain either
    output text or tool calls". Plain-text output is far more reliable.
    """
    from pydantic_ai import Agent
    from api.llm import _get_model

    return Agent(
        _get_model(),
        output_type=str,
        system_prompt=_INTENT_SYSTEM,
    )


async def classify_intent_llm(query: str, timeout: float = 8.0) -> str | None:
    """Classify intent with one small LLM call. Returns None on any failure
    so the caller can fall back to embedding routing."""
    try:
        result = await asyncio.wait_for(_intent_agent().run(query), timeout=timeout)
        raw = result.output or ""
        # Strip <think>...</think> blocks from Qwen3 thinking mode
        if "</think>" in raw:
            raw = raw[raw.rfind("</think>") + len("</think>"):].strip()
        # Extract the intent label — take the first word that matches a known label
        raw_lower = raw.strip().lower()
        for label in _INTENT_LABELS:
            if label in raw_lower:
                return label
        return None
    except Exception as e:
        logger.warning("LLM intent classification failed, falling back to embeddings: %s", e)
        return None


async def route_query(query: str) -> tuple[str, float]:
    """Classify a query into a route + confidence.

    LLM classifier first (generalizes to any phrasing); embedding router as a
    deterministic fallback when the LLM is disabled or unreachable.
    """
    if _COLOR_REFINEMENT_RE.search(query):
        return "requires_history", 1.0

    if getattr(config, "ROUTER_USE_LLM", True):
        intent = await classify_intent_llm(query)
        if intent:
            return intent, 1.0

    return await _route_query_embeddings(query)


async def _route_query_embeddings(query: str) -> tuple[str, float]:
    """Fallback router: cosine-match the query against example utterances."""
    global _USE_MOCK_EMBED
    if _USE_MOCK_EMBED is None:
        await init_router()

    query_emb = await get_embedding(query)

    best_route = "others"
    best_score = 0.0

    for route_name, utterance_embs in _UTTERANCE_EMBEDDINGS.items():
        for utt_emb in utterance_embs:
            score = _cosine(query_emb, utt_emb)
            if score > best_score:
                best_score = score
                best_route = route_name

    # Threshold tuned per embedding type:
    # - Mock (hash-based): 0.50 — vectors are sparse, high similarity = exact token match
    # - Real (BGE-small): 0.62 — dense vectors, 0.62 is the sweet spot for this 384-dim model
    threshold = 0.50 if _USE_MOCK_EMBED else 0.62
    if best_score < threshold:
        return "others", best_score

    return best_route, best_score
