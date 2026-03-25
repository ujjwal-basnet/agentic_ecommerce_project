"""Rebuild product_description.md from the database.

Called when products are added, updated, or deleted so the
LLM search agent always has an up-to-date catalog.
"""

from pathlib import Path
import database
import config

_CATALOG_PATH = Path(__file__).resolve().parent / "product_description.md"


def _enrich_description(product: dict) -> dict:
    """Use LLM to generate rich keywords, occasions, etc. for a product."""
    if not config.openai_enabled():
        return product

    name = product.get("name", "")
    category = product.get("category", "")
    color = product.get("color", "")
    price = product.get("price", 0)
    desc = product.get("description", "")
    is_wearable = product.get("is_wearable", 0)

    try:
        from llm import call_llm_json
        system = """You enrich product catalog entries for an e-commerce store called SmartShop.
Given basic product info, generate additional metadata.

Return ONLY valid JSON with these fields:
{
  "description": "A 1-2 sentence appealing product description",
  "keywords": ["keyword1", "keyword2", ...],
  "occasions": ["occasion1", "occasion2", ...],
  "material": "material type or empty string",
  "fit": "fit type or empty string",
  "nepali_names": "nepali search terms (romanized) or empty string"
}

Be creative but accurate. Keywords should include the product name, color, category, synonyms, and related search terms people might use."""

        user_msg = f"Product: {name}\nCategory: {category}\nColor: {color}\nPrice: Rs. {price}\nDescription: {desc}\nWearable: {'Yes' if is_wearable else 'No'}"
        result = call_llm_json(system, user_msg)

        if result.get("description") and not desc:
            product["description"] = result["description"]
        elif result.get("description"):
            product["enriched_description"] = result["description"]

        product["keywords"] = result.get("keywords", [])
        product["occasions"] = result.get("occasions", [])
        product["material"] = result.get("material", "")
        product["fit"] = result.get("fit", "")
        product["nepali_names"] = result.get("nepali_names", "")
    except Exception as e:
        print(f"[catalog] LLM enrichment failed for {name}: {e}")

    return product


def regenerate_catalog():
    """Rebuild product_description.md from all products in the database."""
    products = database.get_all_products()
    if not products:
        _CATALOG_PATH.write_text("# SmartShop Product Catalog\n\nNo products available.\n",
                                  encoding="utf-8")
        _invalidate_search_cache()
        return

    lines = [
        "# SmartShop Product Catalog\n",
        "This file contains the complete product catalog for SmartShop. "
        "The AI assistant uses this to understand what products are available, "
        "match user queries intelligently, and provide accurate recommendations.\n",
        "---\n",
    ]

    all_ids = []
    price_ranges = {"under_25": [], "25_to_50": [], "above_50": []}
    colors_map = {}
    categories_map = {}

    for p in products:
        pid = p["id"]
        name = p.get("name", "Unknown")
        category = p.get("category", "")
        color = p.get("color", "")
        price = p.get("price", 0)
        stock = p.get("quantity", 0)
        image = p.get("image_path", "")
        is_wearable = bool(p.get("is_wearable", 0))
        description = p.get("description", "")
        tags = p.get("tags", "[]")

        all_ids.append(pid)

        # Track price ranges
        if price < 25:
            price_ranges["under_25"].append(f"{name} ({price})")
        elif price <= 50:
            price_ranges["25_to_50"].append(f"{name} ({price})")
        else:
            price_ranges["above_50"].append(f"{name} ({price})")

        # Track colors
        if color:
            colors_map.setdefault(color, []).append(name)

        # Track categories
        if category:
            categories_map.setdefault(category, []).append(
                f"{name} — Rs. {price}"
            )

        # Try to parse tags
        try:
            import json
            tag_list = json.loads(tags) if isinstance(tags, str) else tags
        except Exception:
            tag_list = []

        lines.append(f"## Product {pid}: {name}")
        lines.append(f"- **ID**: {pid}")
        lines.append(f"- **Name**: {name}")
        lines.append(f"- **Category**: {category}")
        lines.append(f"- **Color**: {color}")
        lines.append(f"- **Price**: Rs. {price}")
        lines.append(f"- **Stock**: {stock}")
        if image:
            lines.append(f"- **Image**: {image}")
        lines.append(f"- **Wearable**: {'Yes (try-on eligible)' if is_wearable else 'No'}")
        if description:
            lines.append(f"- **Description**: {description}")
        if tag_list:
            lines.append(f"- **Keywords**: {', '.join(str(t) for t in tag_list)}")
        lines.append("")
        lines.append("---\n")

    # Quick Reference Table
    lines.append("## Quick Reference Table\n")
    lines.append("| ID | Name | Color | Price | Category | Wearable |")
    lines.append("|----|------|-------|-------|----------|----------|")
    for p in products:
        w = "Yes" if p.get("is_wearable") else "No"
        lines.append(
            f"| {p['id']} | {p.get('name','')} | {p.get('color','')} "
            f"| {p.get('price',0)} | {p.get('category','')} | {w} |"
        )
    lines.append("")

    # Category Summary
    lines.append("## Category Summary")
    for cat, items in categories_map.items():
        lines.append(f"- **{cat.title()}**: {', '.join(items)}")
    lines.append("")

    # Color Availability
    lines.append("## Color Availability")
    for color, names in colors_map.items():
        lines.append(f"- **{color.title()}**: {', '.join(names)}")
    lines.append("")

    # Price Ranges
    lines.append("## Price Ranges")
    if price_ranges["under_25"]:
        lines.append(f"- **Under Rs. 25**: {', '.join(price_ranges['under_25'])}")
    if price_ranges["25_to_50"]:
        lines.append(f"- **Rs. 25-50**: {', '.join(price_ranges['25_to_50'])}")
    if price_ranges["above_50"]:
        lines.append(f"- **Above Rs. 50**: {', '.join(price_ranges['above_50'])}")
    lines.append("")

    _CATALOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    _invalidate_search_cache()
    print(f"[catalog] Regenerated product_description.md with {len(products)} products")


def _invalidate_search_cache():
    """Clear the search agent's cached catalog so it reloads."""
    try:
        import agents.search as search_mod
        search_mod._catalog_cache = None
    except Exception:
        pass


def enrich_and_regenerate(product_id: int):
    """Enrich a single product's description via LLM, then regenerate the full catalog."""
    p = database.get_product_by_id(product_id)
    if not p:
        return

    enriched = _enrich_description(dict(p))

    # Update DB with enriched description if we got one
    updates = {}
    if enriched.get("enriched_description"):
        updates["description"] = enriched["enriched_description"]
    elif enriched.get("description") and not p.get("description"):
        updates["description"] = enriched["description"]

    # Build tags from keywords
    keywords = enriched.get("keywords", [])
    if keywords:
        import json
        updates["tags"] = json.dumps(keywords)

    if updates:
        database.update_product(product_id, **updates)

    regenerate_catalog()
