"""Owner dashboard API routes — analytics, products CRUD, facebook."""

from __future__ import annotations
import json
import os
from fastapi import APIRouter, UploadFile, File, Form
import database
import catalog_generator

router = APIRouter(prefix="/owner")


@router.get("/analytics")
async def get_analytics(days: int = 30):
    stats = database.get_summary_stats()
    revenue = database.get_revenue_by_day(days)
    top = database.get_top_products(5)
    by_cat = database.get_revenue_by_category()
    stock = database.get_stock_levels()
    orders = database.get_recent_orders(10)
    return {
        "stats": stats, "revenue": revenue, "top": top,
        "by_cat": by_cat, "stock": stock, "orders": orders,
    }


@router.get("/products")
async def list_products():
    return database.get_all_products()


@router.post("/products/new")
async def new_product(
    name: str = Form(),
    category: str = Form(),
    price: float = Form(),
    quantity: int = Form(),
    color: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    is_wearable: bool = Form(False),
):
    image_path = ""
    if image:
        contents = await image.read()
        ext = os.path.splitext(image.filename or "product")[1] or ".jpg"
        image_path = database.save_product_image(contents, name, ext)

    pid = database.insert_product(
        name=name, category=category, color=color, price=price,
        description=description, quantity=quantity,
        image_path=image_path, tags="[]", is_wearable=int(is_wearable),
    )
    # Enrich description via LLM and regenerate catalog
    try:
        catalog_generator.enrich_and_regenerate(pid)
    except Exception as e:
        print(f"[owner] Catalog enrichment failed: {e}")
    return {"success": True, "product_id": pid}


@router.post("/products/delete")
async def delete_product(product_id: int = Form(...)):
    ok = database.delete_product_row(product_id)
    # Regenerate catalog after deletion
    try:
        catalog_generator.regenerate_catalog()
    except Exception as e:
        print(f"[owner] Catalog regeneration failed: {e}")
    return {"ok": ok}


@router.post("/products/update")
async def update_product(
    product_id: int = Form(...),
    name: str = Form(None),
    category: str = Form(None),
    price: float = Form(None),
    quantity: int = Form(None),
    color: str = Form(None),
    description: str = Form(None),
):
    kwargs = {}
    if name is not None: kwargs["name"] = name
    if category is not None: kwargs["category"] = category
    if price is not None: kwargs["price"] = price
    if quantity is not None: kwargs["quantity"] = quantity
    if color is not None: kwargs["color"] = color
    if description is not None: kwargs["description"] = description
    if kwargs:
        database.update_product(product_id, **kwargs)
    return {"success": True}


@router.post("/facebook/post")
async def post_to_facebook(
    image: UploadFile = File(...),
    caption: str = Form(""),
):
    """Post a product image + caption — delegates to specialist agent."""
    from specialist_agents.facebook import post_to_page

    contents = await image.read()
    return post_to_page(
        image_bytes=contents,
        caption=caption,
        filename=image.filename or "post.jpg",
    )
