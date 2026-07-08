#!/usr/bin/env python3
"""Generate SmartShop planner fine-tuning data.

The dataset trains the LLM planner to emit the project's CapabilityPlan JSON.
It does not train final product prose, product cards, database facts, or cart
state. Those are runtime responsibilities of the deterministic engine and
specialist agents.

Outputs:
    data/finetune_dataset.jsonl       all examples; default training input
    data/finetune_train.jsonl         train split
    data/finetune_validation.jsonl    validation prompts for manual checks
    data/finetune_test.jsonl          held-out prompts
    data/finetune_manifest.json       counts and generation notes
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CATALOG_PATH = Path("data/products.md")
OUTPUT_ALL = Path("data/finetune_dataset.jsonl")
OUTPUT_TRAIN = Path("data/finetune_train.jsonl")
OUTPUT_VALIDATION = Path("data/finetune_validation.jsonl")
OUTPUT_TEST = Path("data/finetune_test.jsonl")
OUTPUT_MANIFEST = Path("data/finetune_manifest.json")

CHANNELS = ("web", "mcp", "facebook", "instagram")
SPLITS = ("train", "validation", "test")

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

SYSTEM_TEMPLATE = """You are the SmartShop planner.

Return only one valid CapabilityPlan JSON object. Do not include markdown.
Use short descriptions and a concise overall_strategy; do not write hidden
chain-of-thought.

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

Routing rules:
- Product browsing, availability, stock, price, comparison, recommendation,
  and "do you have X" requests must use resolve_products with catalog IDs.
- Product queries use exactly one resolve_products step. Never add
  search_knowledge_base beside a product step.
- search_knowledge_base is only for store policy: delivery, shipping, returns,
  refund, payment, warranty, privacy, and sizing.
- Product filters are AND filters. Color, category, item type, gender and price
  constraints must all match. If no catalog item matches a hard constraint,
  return no steps and a short direct_response.
- Use product IDs only from the catalog. Never invent product IDs.
- For web, the renderer will show product cards and answer text later.
- For MCP, Facebook and Instagram, the renderer sends reply_message text only,
  but the planner still emits the same tool calls.
- Direct greetings and pure small talk use no steps and direct_response only.
- Ask for clarification only when cart or try-on target is truly missing.
"""


@dataclass(frozen=True)
class ProductCase:
    strategy: str
    product_ids: tuple[int, ...]
    train: tuple[str, ...]
    validation: tuple[str, ...] = ()
    test: tuple[str, ...] = ()


def parse_catalog_from_md() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Missing catalog: {CATALOG_PATH}")

    pattern = re.compile(
        r"-\s+id=(\d+)\s+.\s+([^.\n]+?)\s+.\s+Rs\.\s+(\d+)"
        r"\s+.\s+color:\s+([^.\n]+?)\s*(?:.\s+tags:\s+(.+))?$"
    )
    products: list[dict[str, Any]] = []
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
                "price": int(match.group(3)),
                "color": match.group(4).strip(),
                "tags": tags,
            }
        )
    if not products:
        raise RuntimeError(f"No products parsed from {CATALOG_PATH}")
    return products


OLD_ID_TO_NAME_KEYWORD = {
    1: "keyboard",
    2: "harry porter",
    3: "wayfarer",
    4: "pringles",
    5: "royal blue",
    6: "sprite",
    7: "nitro",
    8: "laptop cover bag",
    9: "kurti",
    10: "latitude",
    11: "loq",
    12: "jeans",
    13: "cctv",
    14: "soundbox",
    15: "thunder",
    16: "womens formal shirt",
    17: "power adapter",
    18: "polar fleece",
    19: "dumbbell",
    20: "portable handheld rechargeable fan"
}


def get_id_mapping(products: list[dict[str, Any]]) -> dict[int, int]:
    mapping = {}
    for old_id, keyword in OLD_ID_TO_NAME_KEYWORD.items():
        matched_id = None
        for p in products:
            if keyword in p["name"].lower():
                matched_id = p["id"]
                break
        if matched_id is None:
            raise ValueError(f"Could not map keyword {keyword!r} to any current product")
        mapping[old_id] = matched_id
    return mapping


def build_catalog_text(products: list[dict[str, Any]]) -> str:
    mapping = get_id_mapping(products)
    wearable_old = (2, 5, 9, 12, 16, 18)
    wearable_new = sorted(mapping[i] for i in wearable_old)
    wearable_str = ", ".join(str(i) for i in wearable_new)
    lines = [
        "Catalog source of truth:",
        f"Wearable product IDs for virtual try-on: {wearable_str}.",
    ]
    for product in products:
        tags = ", ".join(str(tag) for tag in product["tags"][:10])
        lines.append(
            f"- id={product['id']} | {product['name']} | Rs. {product['price']} "
            f"| color: {product['color']} | tags: {tags}"
        )
    return "\n".join(lines)


def channel_preamble(channel: str, context: str | None = None) -> str:
    surfaces = {
        "web": ("customer_web_chat", "product_card_and_answer"),
        "mcp": ("mcp_chat_tool", "reply_message_only"),
        "facebook": ("facebook_dm", "reply_message_only"),
        "instagram": ("instagram_dm", "reply_message_only"),
    }
    surface, renderer = surfaces[channel]
    lines = [f"Channel: {channel}", f"Surface: {surface}", f"Renderer: {renderer}"]
    if context:
        lines.extend(["Context:", context])
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


def make_example(
    *,
    system: str,
    channel: str,
    user_request: str,
    target: dict[str, Any],
    context: str | None = None,
) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"{channel_preamble(channel, context)}\nUser request: {user_request}",
            },
            {
                "role": "assistant",
                "content": json.dumps(target, ensure_ascii=False, separators=(",", ":")),
            },
        ]
    }


def assert_ids(products: list[dict[str, Any]], product_ids: Iterable[int]) -> list[int]:
    known = {int(product["id"]) for product in products}
    ids = [int(pid) for pid in product_ids]
    missing = [pid for pid in ids if pid not in known]
    if missing:
        raise ValueError(f"Dataset references missing product IDs: {missing}")
    return ids


def first_words(name: str, count: int) -> str:
    return " ".join(name.split()[:count])


def resolve_target(products: list[dict[str, Any]], product_ids: Iterable[int], strategy: str) -> dict[str, Any]:
    return plan(
        [
            step(
                "resolve_products",
                "Resolve catalog products that satisfy the user request",
                {"product_ids": assert_ids(products, product_ids)},
            )
        ],
        strategy,
    )


def tool_target(
    products: list[dict[str, Any]],
    capability: str,
    parameters: dict[str, Any] | None,
    strategy: str,
) -> dict[str, Any]:
    params = dict(parameters or {})
    if "product_id" in params:
        assert_ids(products, [params["product_id"]])
    if "product_ids" in params:
        params["product_ids"] = assert_ids(products, params["product_ids"])
    return plan([step(capability, strategy, params)], strategy)


def direct_target(response: str, strategy: str) -> dict[str, Any]:
    return plan([], strategy, response)


def add(
    buckets: dict[str, list[dict[str, Any]]],
    split: str,
    *,
    system: str,
    channel: str,
    user_request: str,
    target: dict[str, Any],
    context: str | None = None,
) -> None:
    buckets[split].append(
        make_example(
            system=system,
            channel=channel,
            user_request=user_request,
            target=target,
            context=context,
        )
    )


def product_cases(products: list[dict[str, Any]]) -> list[ProductCase]:
    mapping = get_id_mapping(products)
    
    def m(old_ids: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(mapping[old_id] for old_id in old_ids)

    return [
        ProductCase("Shirt query; return only shirt catalog IDs.", m((2, 5, 16)), ("show me shirts", "do you have tshirts", "any shirt available", "shirt haru cha"), ("show all shirts", "tshirt cha?"), ("i need shirts", "show me some t-shirts")),
        ProductCase("AND filter: red and shirt must both match.", m((2,)), ("red shirt", "do you have any red thisrt", "show me red tshirt", "raat shirt cha"), ("red t shirt available?",), ("i want a red tee",)),
        ProductCase("AND filter: blue and shirt must both match.", m((5,)), ("blue shirt", "royal blue shirt", "do you have blue formal shirt"), ("blue tshirt",), ("shirt in blue color",)),
        ProductCase("Women's wearable products for gift-style request.", m((9, 16)), ("anything for my wife", "clothes for her", "women clothing", "wife lai gift"), ("something for ladies",), ("what do you have for women",)),
        ProductCase("Men's wearable products.", m((2, 5, 12, 18)), ("clothes for men", "anything for husband", "mens wear", "male clothing"), ("outfit for him",), ("men ko lagi kapada",)),
        ProductCase("Kurti/suit product.", m((9,)), ("kurti cha?", "red ladies kurti", "ladies cotton suit", "show me kurti"), ("do you have kurtha",), ("red suit for women",)),
        ProductCase("Jeans product.", m((12,)), ("show me jeans", "light blue jeans", "pants cha", "denim pants"), ("blue jeans available?",), ("jeans for men",)),
        ProductCase("Winter jacket product.", m((18,)), ("winter jacket", "cream black jacket", "jacket for cold", "warm jacket cha"), ("show jacket",), ("do you have a winter coat",)),
        ProductCase("Drink request; return Sprite only and never snacks.", m((6,)), ("do you have sprite", "anything to drink", "drink cha", "cold drink"), ("i think you have drink its sprite?",), ("something for drinking",)),
        ProductCase("Snack request; return Pringles only and never drinks.", m((4,)), ("i want snacks", "chips cha", "pringles available", "snack item"), ("show me chips",), ("something to eat as snack",)),
        ProductCase("Summer utility recommendation from catalog.", m((20, 6, 3)), ("it is too hot anything for summer", "summer products", "fan or cold drink", "garmi ko lagi ke cha"), ("recommend summer items",), ("anything useful in hot weather",)),
        ProductCase("Budget filter below Rs. 600.", m((3,)), ("anything under 600", "under rs 600", "cheap product below 600", "600 bhanda tala"), ("show products less than 600",), ("what can i buy below rs 600",)),
        ProductCase("Budget filter below Rs. 1000.", m((3, 4, 6, 1, 20)), ("products under 1000", "anything below rs 1000", "cheap items under 1k"), ("show under 1000 rupees",), ("what do you sell below one thousand",)),
        ProductCase("Laptop/accessory budget filter below Rs. 50000.", m((8, 10)), ("laptop under 50000", "computer under 50k", "cheap laptop below 50000"), ("laptops below rs 50000",), ("budget laptop under fifty thousand",)),
        ProductCase("Laptop category query.", m((7, 10, 11)), ("show me laptops", "laptop cha?", "computer models", "notebook computer"), ("do you have acer or dell laptop",), ("all laptops available",)),
        ProductCase("Laptop accessories are not laptops, but match accessory request.", m((8,)), ("laptop bag", "laptop cover", "bag for laptop", "black laptop cover bag"), ("do you have laptop sleeve",), ("cover for laptop",)),
        ProductCase("Speaker products.", m((14, 15)), ("bluetooth speaker", "show speakers", "black speaker", "music speaker"), ("do you have thunder speaker",), ("speaker for music",)),
        ProductCase("Camera/security product.", m((13,)), ("cctv camera", "security camera", "white camera", "do you have camera"), ("camera for home",), ("surveillance camera available?",)),
        ProductCase("Charger/adapter product.", m((17,)), ("iphone charger", "usb c charger", "adapter cha", "white charger"), ("type c adapter",), ("charging adapter",)),
        ProductCase("Fitness product.", m((19,)), ("gym equipment", "dumbbell set", "red dumbbell", "fitness item"), ("workout product",), ("do you have weights",)),
        ProductCase("Fan product.", m((20,)), ("fan cha", "portable fan", "rechargeable fan", "green fan"), ("show me fan",), ("cheap fan",)),
        ProductCase("Keyboard product.", m((1,)), ("keyboard cha", "dell keyboard", "black keyboard", "computer keyboard"), ("show keyboard",), ("keyboard under 1000",)),
        ProductCase("Sunglasses/accessory product.", m((3,)), ("sunglasses", "black goggles", "sun glasses", "chasma cha"), ("glasses for sun",), ("black sunglasses available?",)),
        ProductCase("Mixed useful recommendation; choose catalog products directly.", m((20, 17, 1, 3)), ("recommend something useful", "suggest useful items", "what should i buy", "malai ke recommend garchau"), ("recommend practical products",), ("give me a few useful options",)),
        ProductCase("Mixed gift recommendation; choose catalog products directly.", m((9, 16, 18, 3)), ("gift recommendation", "gift for family", "suggest a gift", "birthday gift option"), ("recommend a gift for my sister",), ("gift ideas from your store",)),
    ]


def add_product_examples(buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    for case in product_cases(products):
        for channel in CHANNELS:
            for request in case.train:
                add(buckets, "train", system=system, channel=channel, user_request=request, target=resolve_target(products, case.product_ids, case.strategy))
        for request in case.validation:
            for channel in ("web", "facebook"):
                add(buckets, "validation", system=system, channel=channel, user_request=request, target=resolve_target(products, case.product_ids, case.strategy))
        for request in case.test:
            for channel in ("web", "instagram"):
                add(buckets, "test", system=system, channel=channel, user_request=request, target=resolve_target(products, case.product_ids, case.strategy))

    for product in products:
        variants = {
            "train": (f"do you have {first_words(product['name'], 3)}", f"price of {first_words(product['name'], 4)}", f"show {first_words(product['name'], 2)}"),
            "validation": (f"is {first_words(product['name'], 3)} available?",),
            "test": (f"tell me about {first_words(product['name'], 4)}",),
        }
        for split, requests in variants.items():
            channels = CHANNELS if split == "train" else ("web", "mcp")
            for request in requests:
                for channel in channels:
                    add(
                        buckets,
                        split,
                        system=system,
                        channel=channel,
                        user_request=request,
                        target=resolve_target(products, (product["id"],), "Resolve the named catalog product so runtime can answer from live data."),
                    )

    no_match = [
        ("do you have coca cola?", "I couldn't find a matching product in the current catalog."),
        ("show me red laptop", "I couldn't find a matching product in the current catalog."),
        ("do you have shoes?", "I couldn't find a matching product in the current catalog."),
        ("blue kurti under 500", "I couldn't find a matching product in the current catalog."),
        ("green shirt", "I couldn't find a matching product in the current catalog."),
        ("white dumbbell", "I couldn't find a matching product in the current catalog."),
        ("iphone mobile phone", "I couldn't find a matching product in the current catalog."),
        ("red speaker", "I couldn't find a matching product in the current catalog."),
        ("shirt under 500", "I couldn't find a matching product in the current catalog."),
        ("laptop under 10000", "I couldn't find a matching product in the current catalog."),
        ("black kurti", "I couldn't find a matching product in the current catalog."),
        ("yellow jacket", "I couldn't find a matching product in the current catalog."),
    ]
    for index, (request, response) in enumerate(no_match):
        split = "train" if index < 8 else "validation" if index < 10 else "test"
        channels = CHANNELS if split == "train" else ("web", "facebook")
        for channel in channels:
            add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=request,
                target=direct_target(response, "No catalog product satisfies all hard product constraints."),
            )


def add_context_examples(buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    mapping = get_id_mapping(products)
    examples = [
        ("train", "web", "red one", f"Recent conversation: user asked for shirts; assistant showed ids {mapping[2]}, {mapping[5]}, {mapping[16]}.", (mapping[2],), "Use prior shirt results and apply color refinement."),
        ("train", "facebook", "how much is this?", f"Recent conversation: assistant showed Sprite Lemon & Lime Flavoured, id {mapping[6]}, Rs. 999.", (mapping[6],), "Resolve referenced product so response builder can answer price."),
        ("train", "instagram", "can i drink this?", f"Recent conversation: assistant showed Sprite Lemon & Lime Flavoured, id {mapping[6]}.", (mapping[6],), "Resolve referenced drink product."),
        ("train", "mcp", "blue wala", f"Recent conversation: assistant showed shirt ids {mapping[2]}, {mapping[5]}, {mapping[16]}.", (mapping[5],), "Resolve color reference from recent product cards."),
        ("validation", "web", "the cheaper laptop", f"Recent conversation: assistant showed laptop ids {mapping[7]}, {mapping[10]}, {mapping[11]}.", (mapping[10],), "Resolve comparative reference using recent product set."),
        ("test", "instagram", "is this wearable?", f"Recent conversation: assistant showed Red Ladies Cotton Kurti suit, id {mapping[9]}.", (mapping[9],), "Resolve referenced wearable product."),
    ]
    for split, channel, request, context, ids_, strategy in examples:
        add(buckets, split, system=system, channel=channel, user_request=request, target=resolve_target(products, ids_, strategy), context=context)


def add_cart_examples(buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    mapping = get_id_mapping(products)
    cart_cases = [
        ("train", "web", "add harry potter shirt", "add_to_cart", {"product_id": mapping[2], "quantity": 1}),
        ("train", "facebook", "add two sprite", "add_to_cart", {"product_id": mapping[6], "quantity": 2}),
        ("train", "instagram", "add 3 pringles", "add_to_cart", {"product_id": mapping[4], "quantity": 3}),
        ("train", "mcp", "add dell keyboard to cart", "add_to_cart", {"product_id": mapping[1], "quantity": 1}),
        ("train", "web", "remove blue shirt", "remove_from_cart", {"product_id": mapping[5]}),
        ("train", "facebook", "remove sprite", "remove_from_cart", {"product_id": mapping[6]}),
        ("train", "web", "show my cart", "view_cart", {}),
        ("train", "instagram", "cart herna paryo", "view_cart", {}),
        ("train", "mcp", "clear cart", "clear_cart", {}),
        ("train", "web", "checkout", "checkout_cart", {}),
        ("train", "facebook", "place order", "checkout_cart", {}),
        ("validation", "web", "add the blue one to cart", "add_to_cart", {"product_id": mapping[5], "quantity": 1}),
        ("validation", "mcp", "remove that charger", "remove_from_cart", {"product_id": mapping[17]}),
        ("test", "web", "buy now", "checkout_cart", {}),
        ("test", "instagram", "add red kurti", "add_to_cart", {"product_id": mapping[9], "quantity": 1}),
    ]
    contexts = {
        "add the blue one to cart": f"Recent conversation: assistant showed shirt ids {mapping[2]}, {mapping[5]}, {mapping[16]}.",
        "remove that charger": f"Recent conversation: current cart has USB-C Fast Charging Adapter, id {mapping[17]}.",
    }
    for split, channel, request, capability, params in cart_cases:
        add(buckets, split, system=system, channel=channel, user_request=request, target=tool_target(products, capability, params, "Cart or checkout action."), context=contexts.get(request))

    for channel in CHANNELS:
        add(buckets, "train", system=system, channel=channel, user_request="add it to cart", target=direct_target("Which product should I add to your cart?", "Ambiguous cart target."))


def add_try_on_examples(buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    mapping = get_id_mapping(products)
    try_on_cases = [
        ("train", "web", "try on the red shirt", mapping[2], "User image path: /tmp/uploads/user-photo.jpg"),
        ("train", "web", "try on the winter jacket", mapping[18], "User image path: /tmp/uploads/user-photo.jpg"),
        ("train", "web", "try on this kurti", mapping[9], f"User image path: /tmp/uploads/user-photo.jpg\nRecent conversation: assistant showed Red Ladies Cotton Kurti suit, id {mapping[9]}."),
        ("validation", "web", "virtual try on blue shirt", mapping[5], "User image path: /tmp/uploads/user-photo.jpg"),
        ("test", "web", "make me wear the jeans", mapping[12], "User image path: /tmp/uploads/user-photo.jpg"),
    ]
    for split, channel, request, product_id, context in try_on_cases:
        add(
            buckets,
            split,
            system=system,
            channel=channel,
            user_request=request,
            target=tool_target(products, "perform_virtual_try_on", {"product_id": product_id}, "Virtual try-on for a wearable product with user photo available."),
            context=context,
        )

    direct_cases = [
        ("train", "web", "try on the dumbbell", "Virtual try-on is only available for wearable products like shirts, jeans, kurtis, and jackets.", "Reject non-wearable try-on target.", None),
        ("train", "web", "try on the red shirt", "Please upload your photo first so I can create the virtual try-on.", "Ask for missing photo before try-on.", "User image path: none"),
        ("validation", "web", "try on the speaker", "Virtual try-on is only available for wearable products like shirts, jeans, kurtis, and jackets.", "Reject non-wearable try-on target.", None),
    ]
    for split, channel, request, response, strategy, context in direct_cases:
        add(buckets, split, system=system, channel=channel, user_request=request, target=direct_target(response, strategy), context=context)


def add_policy_examples(buckets: dict[str, list[dict[str, Any]]], system: str) -> None:
    cases = [
        ("what is your delivery policy?", "delivery policy"),
        ("how many days outside kathmandu?", "delivery outside Kathmandu Valley"),
        ("do you support cash on delivery?", "cash on delivery"),
        ("what is your return policy?", "return policy"),
        ("refund kasari huncha?", "refund policy"),
        ("what payment methods do you accept?", "payment methods"),
        ("do you have warranty?", "warranty policy"),
        ("is my data private?", "privacy policy"),
        ("size chart for shirts", "sizing guide"),
        ("do you deliver to my wife in Pokhara?", "delivery policy for Pokhara"),
        ("delivery kati din lagcha?", "delivery time"),
        ("can i pay with esewa?", "eSewa payment"),
    ]
    for index, (request, query) in enumerate(cases):
        split = "train" if index < 9 else "validation" if index < 11 else "test"
        channels = CHANNELS if split == "train" else ("web", "instagram")
        for channel in channels:
            add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=request,
                target=plan([step("search_knowledge_base", "Look up the relevant store policy answer", {"query": query})], "Policy question; use knowledge base only."),
            )


def add_direct_examples(buckets: dict[str, list[dict[str, Any]]], system: str) -> None:
    direct_cases = [
        ("hi", "Hi! What can I help you find today?", "Greeting."),
        ("hello", "Hi! What can I help you find today?", "Greeting."),
        ("wassup", "Hey! What can I help you find today?", "Casual greeting."),
        ("how are you", "I'm doing well. What can I help you find today?", "Small talk."),
        ("thanks", "You're welcome.", "Acknowledgement."),
        ("thank you", "You're welcome.", "Acknowledgement."),
        ("namaste", "Namaste! Tapailai ke khojna madat garu?", "Nepali greeting."),
        ("ke cha", "Thik cha. Tapailai ke product khojna madat garu?", "Romanized Nepali small talk."),
    ]
    for request, response, strategy in direct_cases:
        for channel in CHANNELS:
            add(buckets, "train", system=system, channel=channel, user_request=request, target=direct_target(response, strategy))

    off_topic = [
        "write my Python assignment",
        "hack someone's facebook account",
        "what is the capital of France?",
        "solve this calculus problem",
        "tell me politics news",
        "generate movie script",
    ]
    for index, request in enumerate(off_topic):
        split = "train" if index < 4 else "test"
        channels = ("facebook", "instagram") if split == "train" else ("web",)
        for channel in channels:
            add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=request,
                target=direct_target("I can help with SmartShop products, cart, orders, delivery, and returns.", "Redirect off-topic message to store scope."),
            )


def generate_buckets() -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    products = parse_catalog_from_md()
    system = SYSTEM_TEMPLATE.format(catalog=build_catalog_text(products))
    buckets: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}

    add_product_examples(buckets, system, products)
    add_context_examples(buckets, system, products)
    add_cart_examples(buckets, system, products)
    add_try_on_examples(buckets, system, products)
    add_policy_examples(buckets, system)
    add_direct_examples(buckets, system)

    return buckets, products


def dedupe_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for example in examples:
        key = (example["messages"][1]["content"], example["messages"][2]["content"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(example)
    return deduped


def validate_with_schema(target: dict[str, Any]) -> None:
    try:
        from api.engine.schemas import CapabilityPlan
    except Exception:
        return
    CapabilityPlan.model_validate(target)


def validate_dataset(examples: list[dict[str, Any]], products: list[dict[str, Any]]) -> None:
    known_ids = {int(product["id"]) for product in products}
    for line_no, example in enumerate(examples, start=1):
        messages = example.get("messages") or []
        if [message.get("role") for message in messages] != ["system", "user", "assistant"]:
            raise ValueError(f"Example {line_no}: expected system/user/assistant roles")

        target = json.loads(messages[2]["content"])
        validate_with_schema(target)
        steps = target.get("steps")
        if not isinstance(steps, list):
            raise ValueError(f"Example {line_no}: steps must be a list")
        if steps and target.get("direct_response"):
            raise ValueError(f"Example {line_no}: tool plans must not include direct_response")

        for raw_step in steps:
            capability = raw_step.get("capability")
            if capability not in ALLOWED_CAPABILITIES:
                raise ValueError(f"Example {line_no}: unsupported capability {capability!r}")
            params = raw_step.get("parameters") or {}
            for product_id in params.get("product_ids", []):
                if int(product_id) not in known_ids:
                    raise ValueError(f"Example {line_no}: unknown product_id {product_id}")
            if "product_id" in params and int(params["product_id"]) not in known_ids:
                raise ValueError(f"Example {line_no}: unknown product_id {params['product_id']}")


def output_name(example: dict[str, Any]) -> str:
    target = json.loads(example["messages"][2]["content"])
    if not target["steps"]:
        return "direct_response"
    return target["steps"][0]["capability"]


def channel_name(example: dict[str, Any]) -> str:
    match = re.search(r"^Channel:\s+(.+)$", example["messages"][1]["content"], flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def write_jsonl(path: Path, examples: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")


def write_manifest(buckets: dict[str, list[dict[str, Any]]], all_examples: list[dict[str, Any]]) -> None:
    manifest = {
        "description": "SmartShop CapabilityPlan fine-tuning dataset.",
        "format": "OpenAI/Qwen chat JSONL with system, user and assistant messages.",
        "main_training_file": str(OUTPUT_ALL),
        "split_files": {
            "train": str(OUTPUT_TRAIN),
            "validation": str(OUTPUT_VALIDATION),
            "test": str(OUTPUT_TEST),
        },
        "counts": {"all": len(all_examples), **{split: len(examples) for split, examples in buckets.items()}},
        "channels": dict(sorted(Counter(channel_name(example) for example in all_examples).items())),
        "outputs": dict(sorted(Counter(output_name(example) for example in all_examples).items())),
        "notes": [
            "The assistant target is planner JSON, not the final customer-facing reply.",
            "Web examples identify product_card_and_answer rendering in the user preamble.",
            "MCP, Facebook and Instagram examples identify reply_message_only rendering.",
            "No-match examples intentionally use direct_response to avoid partial product matches.",
            "Policy examples route to search_knowledge_base and product examples route to resolve_products.",
        ],
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    buckets, products = generate_buckets()
    for split in SPLITS:
        buckets[split] = dedupe_examples(buckets[split])

    all_examples = dedupe_examples([example for split in SPLITS for example in buckets[split]])
    validate_dataset(all_examples, products)

    write_jsonl(OUTPUT_ALL, all_examples)
    write_jsonl(OUTPUT_TRAIN, buckets["train"])
    write_jsonl(OUTPUT_VALIDATION, buckets["validation"])
    write_jsonl(OUTPUT_TEST, buckets["test"])
    write_manifest(buckets, all_examples)

    print(f"Generated {len(all_examples)} examples -> {OUTPUT_ALL}")
    print("Splits:", {split: len(examples) for split, examples in buckets.items()})
    print("Channels:", dict(sorted(Counter(channel_name(example) for example in all_examples).items())))
    print("Outputs:", dict(sorted(Counter(output_name(example) for example in all_examples).items())))
    print(f"Manifest: {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()
