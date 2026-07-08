"""Generate the SmartShop tool-call fine-tuning dataset.

The dataset trains planner behavior, not product memorization. Product facts
still come from data/products.md at runtime. Each example teaches:

- exact CapabilityPlan JSON shape
- correct capability choice
- correct product IDs from the current catalog
- channel-aware behavior: web renders product cards later; MCP/Facebook/
  Instagram only receive the final text reply, but the planner still emits the
  same product/cart/policy tool calls.

Output:
    data/finetune_dataset.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


OUTPUT_PATH = Path("data/finetune_dataset.jsonl")
CATALOG_PATH = Path("data/products.md")

ALLOWED_CAPABILITIES = {
    "resolve_products",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "clear_cart",
    "checkout_cart",
    "perform_virtual_try_on",
    "recommend_products",
    "search_knowledge_base",
}

SYSTEM_TEMPLATE = """You are the SmartShop tool planner.

Return ONLY one valid CapabilityPlan JSON object.

{catalog}

Allowed capabilities:
- resolve_products(product_ids: list[int])
- add_to_cart(product_id: int, quantity: int)
- remove_from_cart(product_id: int)
- view_cart()
- clear_cart()
- checkout_cart()
- perform_virtual_try_on(product_id: int)
- recommend_products(context: str, limit: int)
- search_knowledge_base(query: str)

Rules:
- For product browsing, availability, price, stock, recommendation, and "do you have X", emit resolve_products with catalog IDs.
- For web chat, the renderer will show product cards plus the answer. Do not emit UI/card fields yourself.
- For MCP, Facebook DM, and Instagram DM, the renderer will send reply_message text only. Still use resolve_products/cart/policy tools when needed.
- search_knowledge_base is only for store policy: delivery, shipping, returns, refund, payment, warranty, privacy, sizing.
- Never use search_knowledge_base for product availability or browsing.
- Product filters are AND filters: color + category + price must all match.
- If no product matches a hard product constraint, use direct_response and no steps.
- Keep plans minimal. Product query: exactly one resolve_products step. Policy query: exactly one search_knowledge_base step.
- Direct greetings/smalltalk: no steps, direct_response only.
- For social channels, keep direct_response short enough to become a DM reply.
"""


def parse_catalog_from_md() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []

    products: list[dict[str, Any]] = []
    pattern = re.compile(
        r"-\s+id=(\d+)\s+·\s+([^·\n]+?)\s+·\s+Rs\.\s+(\d+)"
        r"\s+·\s+color:\s+([^·\n]+?)\s*(?:·\s+tags:\s+(.+))?$"
    )
    for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        tags_raw = (match.group(5) or "[]").strip()
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []
        products.append(
            {
                "id": int(match.group(1)),
                "name": match.group(2).strip(),
                "price": float(match.group(3)),
                "color": match.group(4).strip(),
                "tags": tags,
            }
        )
    return products


def build_catalog_text(products: list[dict[str, Any]]) -> str:
    lines = [
        "CATALOG:",
        "Use only these IDs. Never invent product IDs.",
        "Wearable product IDs: 2, 5, 9, 12, 16, 18.",
    ]
    for product in products:
        tags = ", ".join(product["tags"][:12])
        lines.append(
            f"- id={product['id']} | {product['name']} | "
            f"Rs. {int(product['price'])} | color: {product['color']} | tags: {tags}"
        )
    return "\n".join(lines)


def step(capability: str, description: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "step_id": "s1",
        "capability": capability,
        "description": description,
        "parameters": parameters or {},
    }


def plan(steps: list[dict[str, Any]], strategy: str, direct_response: str | None = None) -> dict[str, Any]:
    return {"steps": steps, "overall_strategy": strategy, "direct_response": direct_response}


def channel_preamble(channel: str, context: str | None = None) -> str:
    surfaces = {
        "web": ("customer_web_chat", "product_card_and_answer"),
        "mcp": ("mcp_chat_tool", "reply_message_only"),
        "facebook": ("facebook_dm", "reply_message_only"),
        "instagram": ("instagram_dm", "reply_message_only"),
    }
    surface, renderer = surfaces.get(channel, (channel, "reply_message_only"))
    lines = [f"Channel: {channel}", f"Surface: {surface}", f"Renderer: {renderer}"]
    if context:
        lines.extend(["Context:", context])
    return "\n".join(lines)


def make_example(system: str, channel: str, user_request: str, target: dict[str, Any], context: str | None = None) -> dict[str, Any]:
    user_content = f"{channel_preamble(channel, context)}\nUser request: {user_request}"
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(target, ensure_ascii=False, separators=(",", ":"))},
        ]
    }


def first_words(name: str, count: int = 4) -> str:
    return " ".join(name.split()[:count])


def ids(products: list[dict[str, Any]], *product_ids: int) -> list[int]:
    known = {p["id"] for p in products}
    missing = [pid for pid in product_ids if pid not in known]
    if missing:
        raise ValueError(f"Dataset references missing product IDs: {missing}")
    return list(product_ids)


def add_resolve(dataset: list[dict[str, Any]], system: str, products: list[dict[str, Any]], channel: str, user_request: str, product_ids: list[int], strategy: str, context: str | None = None) -> None:
    dataset.append(
        make_example(
            system,
            channel,
            user_request,
            plan([step("resolve_products", "Resolve matching catalog products", {"product_ids": ids(products, *product_ids)})], strategy),
            context=context,
        )
    )


def add_direct(dataset: list[dict[str, Any]], system: str, channel: str, user_request: str, response: str, strategy: str = "Direct response", context: str | None = None) -> None:
    dataset.append(make_example(system, channel, user_request, plan([], strategy, response), context=context))


def add_step(dataset: list[dict[str, Any]], system: str, products: list[dict[str, Any]], channel: str, user_request: str, capability: str, parameters: dict[str, Any] | None = None, strategy: str = "Tool call", context: str | None = None) -> None:
    params = parameters or {}
    if "product_id" in params:
        ids(products, int(params["product_id"]))
    dataset.append(make_example(system, channel, user_request, plan([step(capability, strategy, params)], strategy), context=context))


def generate_dataset() -> list[dict[str, Any]]:
    products = parse_catalog_from_md()
    if not products:
        raise RuntimeError("No products found in data/products.md")
    system = SYSTEM_TEMPLATE.format(catalog=build_catalog_text(products))
    dataset: list[dict[str, Any]] = []

    for channel in ["web", "mcp", "facebook", "instagram"]:
        add_direct(dataset, system, channel, "hi", "Hi! What can I help you find today?", "Greeting")
        add_direct(dataset, system, channel, "how r you?", "I'm doing well. What can I help you find today?", "Smalltalk")
        add_direct(dataset, system, channel, "thanks", "You're welcome.", "Acknowledgement")

    product_cases = [
        ("show me shirts", [2, 5, 16], "All shirt products"),
        ("do you have tshirts?", [2, 5, 16], "Shirt query with tshirt spelling"),
        ("do you have any red thisrt?", [2], "Typo corrected: red shirt"),
        ("red shirt", [2], "AND filter: red + shirt"),
        ("blue shirt", [5], "AND filter: blue + shirt"),
        ("shirts for men", [2, 5], "Men's shirts"),
        ("anything for my wife?", [9, 16], "Women's products, not policy"),
        ("clothes for her", [9, 16], "Women's wearable products"),
        ("clothes for him", [2, 5, 12, 18], "Men's wearable products"),
        ("winter jacket", [18], "Jacket product"),
        ("show me jeans", [12], "Jeans product"),
        ("do you have sprite?", [6], "Drink product"),
        ("anything to drink?", [6], "Drink only, do not include snacks"),
        ("i want snacks", [4], "Snack only, do not include drinks"),
        ("do you have chips?", [4], "Snack chips product"),
        ("do you have a fan?", [20], "Fan product"),
        ("it is too hot, anything for summer?", [20, 6, 3], "Summer products"),
        ("anything under 500rs?", [20], "Exact budget filter under Rs. 500"),
        ("products under rs 1000", [3, 4, 6, 1, 20], "Price filter under Rs. 1000"),
        ("show me electronics", [13, 14, 15, 17, 20], "Electronics-like products"),
        ("iphone charger", [17], "Charger product"),
        ("usb c adapter", [17], "Adapter product"),
        ("gym equipment", [19], "Fitness product"),
        ("dumbbell set", [19], "Dumbbell product"),
        ("bluetooth speaker", [14, 15], "Speaker products"),
        ("cctv camera", [13], "Camera product"),
        ("black accessories", [3], "Black accessory, not every black item"),
        ("white charger", [17], "White + charger AND filter"),
        ("red dumbbell", [19], "Red + dumbbell AND filter"),
    ]
    for channel in ["web", "mcp", "facebook", "instagram"]:
        for user_request, product_ids, strategy in product_cases:
            add_resolve(dataset, system, products, channel, user_request, product_ids, strategy)

    for item in products:
        add_resolve(dataset, system, products, "web", f"do you have {first_words(item['name'])}?", [item["id"]], "Resolve by partial product name")
        add_resolve(dataset, system, products, "facebook", f"price of {first_words(item['name'], 3)}", [item["id"]], "Resolve product so reply generator can answer price in text")

    add_resolve(dataset, system, products, "web", "red one", [2], "Resolve color refinement from prior shirt cards", context="Recent conversation: user asked for shirts; assistant showed ids 2, 5, 16.")
    add_resolve(dataset, system, products, "instagram", "what is the price of this?", [6], "Resolve referenced product for attribute answer", context="Recent conversation: assistant showed Sprite Lemon & Lime Flavoured, id 6, Rs. 999.")
    add_resolve(dataset, system, products, "facebook", "can i drink this?", [6], "Resolve referenced drink for attribute answer", context="Recent conversation: assistant showed Sprite Lemon & Lime Flavoured, id 6.")
    add_step(dataset, system, products, "web", "add the blue one to cart", "add_to_cart", {"product_id": 5, "quantity": 1}, "Cart action", context="Recent conversation: assistant showed shirt ids 2, 5, 16.")

    add_step(dataset, system, products, "web", "add harry potter shirt", "add_to_cart", {"product_id": 2, "quantity": 1}, "Cart action")
    add_step(dataset, system, products, "facebook", "add two sprite", "add_to_cart", {"product_id": 6, "quantity": 2}, "Cart action")
    add_step(dataset, system, products, "instagram", "remove blue shirt", "remove_from_cart", {"product_id": 5}, "Cart action")
    add_step(dataset, system, products, "mcp", "show my cart", "view_cart", strategy="Cart action")
    add_step(dataset, system, products, "web", "clear cart", "clear_cart", strategy="Cart action")
    add_step(dataset, system, products, "web", "checkout", "checkout_cart", strategy="Checkout")
    add_step(dataset, system, products, "facebook", "place order", "checkout_cart", strategy="Checkout")

    add_step(dataset, system, products, "web", "try on the red shirt", "perform_virtual_try_on", {"product_id": 2}, "Virtual try-on", context="User image path: /tmp/uploads/user-photo.jpg")
    add_step(dataset, system, products, "web", "try on the winter jacket", "perform_virtual_try_on", {"product_id": 18}, "Virtual try-on", context="User image path: /tmp/uploads/user-photo.jpg")
    add_direct(dataset, system, "web", "try on the dumbbell", "Virtual try-on is only available for wearable products like shirts, jeans, kurtis, and jackets.", "Reject non-wearable try-on")
    add_direct(dataset, system, "web", "try on the red shirt", "Please upload your photo first so I can create the virtual try-on.", "Ask for missing photo", context="User image path: none")

    policies = [
        ("what is your delivery policy?", "delivery policy"),
        ("how many days outside kathmandu?", "delivery outside Kathmandu Valley"),
        ("do you support cash on delivery?", "cash on delivery"),
        ("what is your return policy?", "return policy"),
        ("what payment methods do you accept?", "payment methods"),
        ("do you have warranty?", "warranty policy"),
        ("is my data private?", "privacy policy"),
        ("size chart for shirts", "sizing guide"),
        ("do you deliver to my wife in Pokhara?", "delivery policy for Pokhara"),
    ]
    for channel in ["web", "mcp", "facebook", "instagram"]:
        for user_request, query in policies:
            dataset.append(make_example(system, channel, user_request, plan([step("search_knowledge_base", "Look up store policy", {"query": query})], "Policy question")))

    for user_request in ["do you have coca cola?", "show me red laptop", "do you have shoes?", "blue kurti under 500"]:
        add_direct(dataset, system, "web", user_request, "I couldn't find a matching product in the current catalog.", "No product satisfies the stated catalog constraint")

    add_resolve(dataset, system, products, "web", "recommend something", [20, 3, 6, 14, 16], "Diverse recommendation")
    add_resolve(dataset, system, products, "mcp", "recommend something useful", [20, 17, 1, 3], "Utility-focused recommendation")
    add_resolve(dataset, system, products, "web", "recommend something else", [17, 18, 19, 14], "Rotate recommendations away from previously shown items", context="Recent conversation: assistant showed ids 20, 3, 6, 14, 16.")

    for user_request in ["write my Python assignment", "hack someone's facebook account", "what is the capital of France?", "solve this calculus problem"]:
        add_direct(dataset, system, "facebook", user_request, "I can help with SmartShop products, cart, orders, delivery, and returns.", "Redirect off-topic social message")

    return dataset


def validate_dataset(dataset: list[dict[str, Any]], products: list[dict[str, Any]]) -> None:
    known_ids = {p["id"] for p in products}
    for line_no, example in enumerate(dataset, start=1):
        messages = example.get("messages") or []
        if len(messages) != 3:
            raise ValueError(f"Line {line_no}: expected 3 chat messages")
        target = json.loads(messages[2]["content"])
        if not isinstance(target.get("steps"), list):
            raise ValueError(f"Line {line_no}: steps must be a list")
        for raw_step in target["steps"]:
            cap = raw_step.get("capability")
            if cap not in ALLOWED_CAPABILITIES:
                raise ValueError(f"Line {line_no}: unsupported capability {cap!r}")
            params = raw_step.get("parameters") or {}
            for pid in params.get("product_ids", []):
                if int(pid) not in known_ids:
                    raise ValueError(f"Line {line_no}: unknown product id {pid}")
            if "product_id" in params and int(params["product_id"]) not in known_ids:
                raise ValueError(f"Line {line_no}: unknown product id {params['product_id']}")


def main() -> None:
    products = parse_catalog_from_md()
    dataset = generate_dataset()
    validate_dataset(dataset, products)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for example in dataset:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    channel_counts: dict[str, int] = {}
    capability_counts: dict[str, int] = {}
    for example in dataset:
        user = example["messages"][1]["content"]
        match = re.search(r"^Channel:\s+(.+)$", user, flags=re.MULTILINE)
        channel = match.group(1) if match else "unknown"
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
        target = json.loads(example["messages"][2]["content"])
        if not target["steps"]:
            capability_counts["direct_response"] = capability_counts.get("direct_response", 0) + 1
        for raw_step in target["steps"]:
            cap = raw_step["capability"]
            capability_counts[cap] = capability_counts.get(cap, 0) + 1

    print(f"Generated {len(dataset)} examples -> {OUTPUT_PATH}")
    print("By channel:", dict(sorted(channel_counts.items())))
    print("By output:", dict(sorted(capability_counts.items())))


if __name__ == "__main__":
    main()
