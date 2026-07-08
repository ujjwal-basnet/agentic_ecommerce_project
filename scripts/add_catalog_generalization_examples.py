#!/usr/bin/env python3
"""Add synthetic product-md catalogs to the planner fine-tuning dataset.

These examples prevent the model from only memorizing the current demo product
IDs. Each row includes a different mini catalog in the system prompt and the
assistant target remains only a CapabilityPlan tool-call JSON object.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


FILES = {
    "all": Path("data/finetune_dataset.jsonl"),
    "train": Path("data/finetune_train.jsonl"),
    "validation": Path("data/finetune_validation.jsonl"),
    "test": Path("data/finetune_test.jsonl"),
}
MANIFEST = Path("data/finetune_manifest.json")

CAPABILITIES = """SUPPORTED CAPABILITIES:
- resolve_products(product_ids: list[int])
- add_to_cart(product_id: int, quantity: int)
- remove_from_cart(product_id: int)
- view_cart()
- clear_cart()
- checkout_cart()
- perform_virtual_try_on(product_id: int)
- search_knowledge_base(query: str)
"""

SYSTEM_TEMPLATE = """Planner for SmartShop.

Synthetic catalog generalization example. Use the product markdown below as the
only source of valid product IDs. Do not memorize IDs from any other catalog.
Return only one CapabilityPlan JSON object.

CATALOG (product index):
{catalog}

{capabilities}
Rules:
- Product browsing, availability, price and recommendation requests use resolve_products.
- Cart requests use cart capabilities with product_id from this catalog.
- Policy requests use search_knowledge_base.
- Product filters are AND filters.
- If no product matches hard constraints, return no steps and a short direct_response.
"""


def step(capability: str, parameters: dict[str, Any], description: str) -> dict[str, Any]:
    return {
        "step_id": "s1",
        "capability": capability,
        "description": description,
        "parameters": parameters,
    }


def plan(steps: list[dict[str, Any]], strategy: str, direct_response: str | None = None) -> dict[str, Any]:
    return {"steps": steps, "overall_strategy": strategy, "direct_response": direct_response}


def row(system: str, user: str, target: dict[str, Any], context: str | None = None) -> dict[str, Any]:
    user_content = f"User request: {user}"
    if context:
        user_content = f"Context:\n{context}\n\n{user_content}"
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(target, ensure_ascii=False, separators=(",", ":"))},
        ]
    }


def product_line(product: dict[str, Any]) -> str:
    tags = json.dumps(product["tags"], ensure_ascii=False)
    return (
        f"- id={product['id']} · {product['name']} · Rs. {product['price']} "
        f"· color: {product['color']} · tags: {tags}"
    )


def make_catalog(offset: int, color_pair: tuple[str, str], drink_name: str) -> list[dict[str, Any]]:
    primary, secondary = color_pair
    return [
        {"id": offset + 1, "name": f"{primary.title()} Cotton Shirt For Men", "price": 1290, "color": primary, "tags": ["shirt", "men", "wearable"]},
        {"id": offset + 2, "name": f"{secondary.title()} Office Shirt For Men", "price": 1390, "color": secondary, "tags": ["shirt", "men", "wearable"]},
        {"id": offset + 3, "name": f"{secondary.title()} Formal Shirt For Women", "price": 1190, "color": secondary, "tags": ["shirt", "women", "ladies", "wearable"]},
        {"id": offset + 4, "name": f"{primary.title()} Ladies Kurti Suit", "price": 1590, "color": primary, "tags": ["kurti", "women", "ladies", "wearable"]},
        {"id": offset + 5, "name": drink_name, "price": 180, "color": "green", "tags": ["drink", "beverage", "cold drink", "summer"]},
        {"id": offset + 6, "name": "Crispy Potato Chips Pack", "price": 220, "color": "yellow", "tags": ["snack", "chips", "food"]},
        {"id": offset + 7, "name": "Rechargeable Mini Fan", "price": 450, "color": "white", "tags": ["fan", "summer", "electronics"]},
        {"id": offset + 8, "name": "Bluetooth Bass Speaker", "price": 3490, "color": "black", "tags": ["speaker", "bluetooth", "electronics"]},
        {"id": offset + 9, "name": "Slim Business Laptop", "price": 47000, "color": "silver", "tags": ["laptop", "computer"]},
        {"id": offset + 10, "name": "Adjustable Dumbbell Pair", "price": 3100, "color": primary, "tags": ["dumbbell", "fitness", "gym"]},
        {"id": offset + 11, "name": "USB C Fast Charger", "price": 990, "color": "white", "tags": ["charger", "adapter", "electronics"]},
    ]


def ids_where(products: list[dict[str, Any]], *, tag: str | None = None, color: str | None = None, max_price: int | None = None) -> list[int]:
    result: list[int] = []
    for product in products:
        tags = {str(item).lower() for item in product["tags"]}
        colors = {part.strip().lower() for part in str(product["color"]).split(",")}
        if tag and tag.lower() not in tags:
            continue
        if color and color.lower() not in colors:
            continue
        if max_price is not None and int(product["price"]) >= max_price:
            continue
        result.append(int(product["id"]))
    return result


def build_examples(split: str, offset: int, color_pair: tuple[str, str], drink_name: str) -> list[dict[str, Any]]:
    products = make_catalog(offset, color_pair, drink_name)
    catalog = "\n".join(product_line(product) for product in products)
    system = SYSTEM_TEMPLATE.format(catalog=catalog, capabilities=CAPABILITIES)
    primary, secondary = color_pair

    shirt_ids = ids_where(products, tag="shirt")
    primary_shirt = ids_where(products, tag="shirt", color=primary)
    secondary_shirt = ids_where(products, tag="shirt", color=secondary)
    women_ids = [pid for pid in ids_where(products, tag="women") + ids_where(products, tag="ladies") if pid]
    women_ids = sorted(set(women_ids))
    drink_ids = ids_where(products, tag="drink")
    snack_ids = ids_where(products, tag="snack")
    cheap_ids = [product["id"] for product in products if product["price"] < 500]
    laptop_ids = ids_where(products, tag="laptop")
    speaker_ids = ids_where(products, tag="speaker")
    dumbbell_ids = ids_where(products, tag="dumbbell")
    charger_ids = ids_where(products, tag="charger")

    examples = [
        row(system, "show me shirts", plan([step("resolve_products", {"product_ids": shirt_ids}, "Resolve shirts from the provided catalog")], "Use catalog tags to select all shirts.")),
        row(system, f"{primary} shirt", plan([step("resolve_products", {"product_ids": primary_shirt}, "Resolve color and category match")], "AND filter: color plus shirt.")),
        row(system, f"{secondary} shirt", plan([step("resolve_products", {"product_ids": secondary_shirt}, "Resolve color and category match")], "AND filter: color plus shirt.")),
        row(system, "anything for my wife", plan([step("resolve_products", {"product_ids": women_ids}, "Resolve women or ladies products")], "Gift-style product request, not policy.")),
        row(system, "anything to drink", plan([step("resolve_products", {"product_ids": drink_ids}, "Resolve drinks only")], "Drink request; do not include snacks.")),
        row(system, "i want snacks", plan([step("resolve_products", {"product_ids": snack_ids}, "Resolve snacks only")], "Snack request; do not include drinks.")),
        row(system, "anything under 500", plan([step("resolve_products", {"product_ids": cheap_ids}, "Resolve products below budget")], "Compute price filter from catalog.")),
        row(system, "show laptops", plan([step("resolve_products", {"product_ids": laptop_ids}, "Resolve laptops")], "Laptop product query.")),
        row(system, "bluetooth speaker", plan([step("resolve_products", {"product_ids": speaker_ids}, "Resolve speakers")], "Speaker product query.")),
        row(system, "gym equipment", plan([step("resolve_products", {"product_ids": dumbbell_ids}, "Resolve fitness products")], "Fitness product query.")),
        row(system, "usb charger", plan([step("resolve_products", {"product_ids": charger_ids}, "Resolve charger products")], "Charger product query.")),
        row(system, "green shirt", plan([], "No catalog product satisfies green plus shirt.", "I couldn't find a matching product in the current catalog.")),
        row(system, f"add {primary} shirt", plan([step("add_to_cart", {"product_id": primary_shirt[0], "quantity": 1}, "Add resolved product to cart")], "Cart action with product resolved from catalog.")),
        row(system, f"add two {drink_name.lower()}", plan([step("add_to_cart", {"product_id": drink_ids[0], "quantity": 2}, "Add resolved product quantity to cart")], "Cart action with quantity.")),
        row(system, "what is your return policy?", plan([step("search_knowledge_base", {"query": "return policy"}, "Look up store policy")], "Policy question.")),
        row(system, f"try on the {primary} shirt", plan([step("perform_virtual_try_on", {"product_id": primary_shirt[0]}, "Perform try-on for wearable product")], "Try-on with uploaded photo."), context="User image path: /tmp/uploads/user-photo.jpg"),
        row(system, "try on the dumbbell", plan([], "Reject non-wearable try-on target.", "Virtual try-on is only available for wearable products like shirts, jeans, kurtis, and jackets.")),
        row(system, f"{primary} one", plan([step("resolve_products", {"product_ids": primary_shirt}, "Resolve referenced color from prior shirt results")], "Use context and catalog to resolve reference."), context=f"Recent conversation: assistant showed shirt ids {shirt_ids}."),
    ]
    return examples


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in rows:
        key = (
            item["messages"][0]["content"],
            item["messages"][1]["content"],
            item["messages"][2]["content"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def output_name(item: dict[str, Any]) -> str:
    target = json.loads(item["messages"][2]["content"])
    if not target["steps"]:
        return "direct_response"
    return target["steps"][0]["capability"]


def update_manifest(rows_by_split: dict[str, list[dict[str, Any]]], added: dict[str, int]) -> None:
    if not MANIFEST.exists():
        return
    all_rows = rows_by_split["all"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["counts"] = {
        "all": len(all_rows),
        "train": len(rows_by_split["train"]),
        "validation": len(rows_by_split["validation"]),
        "test": len(rows_by_split["test"]),
    }
    manifest["outputs"] = dict(sorted(Counter(output_name(item) for item in all_rows).items()))
    manifest["catalog_generalization"] = {
        "added_by": str(Path(__file__)),
        "added_rows": added,
        "purpose": "Teach the planner to choose product_ids from the supplied product markdown instead of memorizing the demo catalog.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    specs = [
        ("train", 1000, ("red", "blue"), "Spark Lemon Drink"),
        ("train", 1100, ("black", "white"), "Mountain Lime Soda"),
        ("train", 1200, ("green", "grey"), "Fresh Orange Drink"),
        ("train", 1300, ("maroon", "navy"), "Cool Cola Drink"),
        ("train", 1400, ("purple", "cream"), "Mint Lemonade"),
        ("train", 1500, ("yellow", "black"), "Icy Mango Drink"),
        ("train", 1600, ("pink", "blue"), "Berry Soda"),
        ("train", 1700, ("teal", "red"), "Lime Fizz Drink"),
        ("validation", 3000, ("red", "white"), "Pear Soda"),
        ("validation", 3100, ("olive", "blue"), "Apple Fizz Drink"),
        ("test", 4000, ("brown", "black"), "Lemon Pop Drink"),
        ("test", 4100, ("cyan", "grey"), "Grape Soda"),
    ]

    current = {name: read_jsonl(path) for name, path in FILES.items()}
    added: dict[str, int] = {"train": 0, "validation": 0, "test": 0}

    for split, offset, colors, drink in specs:
        examples = build_examples(split, offset, colors, drink)
        current[split].extend(examples)
        added[split] += len(examples)

    current["train"] = dedupe(current["train"])
    current["validation"] = dedupe(current["validation"])
    current["test"] = dedupe(current["test"])
    current["all"] = dedupe(current["train"] + current["validation"] + current["test"])

    for name, path in FILES.items():
        write_jsonl(path, current[name])
    update_manifest(current, added)

    print("Added catalog-generalization examples:", added)
    print("Final counts:", {name: len(rows) for name, rows in current.items()})


if __name__ == "__main__":
    main()
