#!/usr/bin/env python3
"""Augment the SmartShop planner dataset with extra non-product-route examples.

The base generator intentionally emphasizes product resolution because that is
the most common customer path. This pass improves class balance for cart,
checkout, policy, reference, no-match and direct-response behavior.
"""

from __future__ import annotations

import importlib.util
import sys
import json
from collections import Counter
from pathlib import Path
from typing import Any


BASE_PATH = Path(__file__).with_name("generate_planner_finetune_dataset.py")


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("planner_dataset_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def add_cart_balance(base: Any, buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    add_templates = [
        ("add {name} to cart", 1),
        ("put {name} in my cart", 1),
        ("add two {short}", 2),
        ("i want 3 {short} in cart", 3),
    ]
    remove_templates = [
        "remove {name} from cart",
        "delete {short} from my cart",
    ]
    channel_cycle = list(base.CHANNELS)

    for product in products:
        name = product["name"]
        short = base.first_words(name, 3)
        product_id = product["id"]

        for index, (template, qty) in enumerate(add_templates):
            channel = channel_cycle[(product_id + index) % len(channel_cycle)]
            split = "train" if index < 3 else "validation"
            base.add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=template.format(name=name.lower(), short=short.lower()),
                target=base.tool_target(
                    products,
                    "add_to_cart",
                    {"product_id": product_id, "quantity": qty},
                    "Explicit cart add action with resolved catalog product.",
                ),
            )

        for index, template in enumerate(remove_templates):
            channel = channel_cycle[(product_id + index + 2) % len(channel_cycle)]
            split = "train" if index == 0 else "test"
            base.add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=template.format(name=name.lower(), short=short.lower()),
                target=base.tool_target(
                    products,
                    "remove_from_cart",
                    {"product_id": product_id},
                    "Explicit cart remove action with resolved catalog product.",
                ),
            )

    cart_misc = [
        ("train", "web", "what is in my cart", "view_cart", {}),
        ("train", "mcp", "cart status", "view_cart", {}),
        ("train", "facebook", "mero cart dekha", "view_cart", {}),
        ("validation", "instagram", "show cart items", "view_cart", {}),
        ("test", "web", "can you list my cart", "view_cart", {}),
        ("train", "web", "empty my cart", "clear_cart", {}),
        ("train", "facebook", "remove everything from cart", "clear_cart", {}),
        ("validation", "mcp", "clear all cart items", "clear_cart", {}),
        ("test", "instagram", "cart khali gara", "clear_cart", {}),
        ("train", "web", "confirm order", "checkout_cart", {}),
        ("train", "facebook", "proceed to checkout", "checkout_cart", {}),
        ("train", "instagram", "order place gara", "checkout_cart", {}),
        ("validation", "mcp", "finalize purchase", "checkout_cart", {}),
        ("test", "web", "complete checkout", "checkout_cart", {}),
    ]
    for split, channel, request, capability, params in cart_misc:
        base.add(
            buckets,
            split,
            system=system,
            channel=channel,
            user_request=request,
            target=base.tool_target(products, capability, params, "Cart or checkout action."),
        )


def add_policy_and_trap_balance(base: Any, buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    mapping = base.get_id_mapping(products)
    m = lambda ids: tuple(mapping[i] for i in ids)

    policy_cases = [
        ("return if size does not fit", "return policy"),
        ("do i get refund after return", "refund policy"),
        ("shipping charge outside valley", "shipping charge outside Kathmandu Valley"),
        ("cod limit kati ho", "cash on delivery limit"),
        ("advance payment kati chahincha", "advance payment policy"),
        ("privacy policy for account", "privacy policy"),
        ("warranty on electronics", "warranty policy"),
        ("delivery in biratnagar", "delivery policy for Biratnagar"),
    ]
    for index, (request, query) in enumerate(policy_cases):
        split = "train" if index < 6 else "validation"
        for channel in ("web", "facebook", "instagram"):
            base.add(
                buckets,
                split,
                system=system,
                channel=channel,
                user_request=request,
                target=base.plan(
                    [
                        base.step(
                            "search_knowledge_base",
                            "Look up the relevant store policy answer",
                            {"query": query},
                        )
                    ],
                    "Policy question; use knowledge base only.",
                ),
            )

    product_policy_traps = [
        ("anything for my wife", m((9, 16)), "Product gift request; do not use delivery policy."),
        ("do you have drinks for delivery", m((6,)), "Product availability query with delivery word; product route wins."),
        ("return me some shirts", m((2, 5, 16)), "Product browsing phrasing; not a return-policy question."),
        ("warranty wala speaker cha?", m((14, 15)), "Product query mentioning warranty word; resolve speaker products."),
    ]
    for request, product_ids, strategy in product_policy_traps:
        for channel in base.CHANNELS:
            base.add(
                buckets,
                "train",
                system=system,
                channel=channel,
                user_request=request,
                target=base.resolve_target(products, product_ids, strategy),
            )


def add_reference_balance(base: Any, buckets: dict[str, list[dict[str, Any]]], system: str, products: list[dict[str, Any]]) -> None:
    mapping = base.get_id_mapping(products)

    references = [
        ("train", "web", "add the first one", f"Recent conversation: assistant showed ids {mapping[2]}, {mapping[5]}, {mapping[16]}.", "add_to_cart", {"product_id": mapping[2], "quantity": 1}),
        ("train", "facebook", "add second one", f"Recent conversation: assistant showed ids {mapping[14]}, {mapping[15]}.", "add_to_cart", {"product_id": mapping[15], "quantity": 1}),
        ("validation", "instagram", "remove the cheap one", f"Recent conversation: current cart has ids {mapping[7]} and {mapping[10]}.", "remove_from_cart", {"product_id": mapping[10]}),
        ("test", "mcp", "checkout this", f"Recent conversation: current cart has id {mapping[6]} quantity 2.", "checkout_cart", {}),
    ]
    for split, channel, request, context, capability, params in references:
        base.add(
            buckets,
            split,
            system=system,
            channel=channel,
            user_request=request,
            target=base.tool_target(products, capability, params, "Use recent context to resolve cart action."),
            context=context,
        )


def add_direct_balance(base: Any, buckets: dict[str, list[dict[str, Any]]], system: str) -> None:
    direct_cases = [
        ("good morning", "Hi! What can I help you find today?", "Greeting."),
        ("ok", "Okay.", "Acknowledgement."),
        ("cool", "Okay.", "Acknowledgement."),
        ("haha", "What can I help you find today?", "Small talk."),
        ("are you a real person", "I'm SmartShop's shopping assistant. What can I help you find today?", "Assistant identity."),
    ]
    for request, response, strategy in direct_cases:
        for channel in base.CHANNELS:
            base.add(
                buckets,
                "train",
                system=system,
                channel=channel,
                user_request=request,
                target=base.direct_target(response, strategy),
            )


def rewrite_outputs(base: Any, buckets: dict[str, list[dict[str, Any]]], products: list[dict[str, Any]]) -> None:
    for split in base.SPLITS:
        buckets[split] = base.dedupe_examples(buckets[split])
    all_examples = base.dedupe_examples([example for split in base.SPLITS for example in buckets[split]])
    base.validate_dataset(all_examples, products)
    base.write_jsonl(base.OUTPUT_ALL, all_examples)
    base.write_jsonl(base.OUTPUT_TRAIN, buckets["train"])
    base.write_jsonl(base.OUTPUT_VALIDATION, buckets["validation"])
    base.write_jsonl(base.OUTPUT_TEST, buckets["test"])
    base.write_manifest(buckets, all_examples)

    manifest = json.loads(base.OUTPUT_MANIFEST.read_text(encoding="utf-8"))
    manifest["augmented_by"] = str(Path(__file__))
    manifest["augmentation_focus"] = [
        "cart and checkout action balance",
        "policy/product routing traps",
        "reference-based cart actions",
        "direct response balance",
    ]
    base.OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Generated {len(all_examples)} examples -> {base.OUTPUT_ALL}")
    print("Splits:", {split: len(examples) for split, examples in buckets.items()})
    print("Outputs:", dict(sorted(Counter(base.output_name(example) for example in all_examples).items())))


def main() -> None:
    base = load_base()
    buckets, products = base.generate_buckets()
    system = base.SYSTEM_TEMPLATE.format(catalog=base.build_catalog_text(products))
    add_cart_balance(base, buckets, system, products)
    add_policy_and_trap_balance(base, buckets, system, products)
    add_reference_balance(base, buckets, system, products)
    add_direct_balance(base, buckets, system)
    rewrite_outputs(base, buckets, products)


if __name__ == "__main__":
    main()
