"""Owner dashboard API routes — analytics, products CRUD, facebook."""

from __future__ import annotations
import json
import os
from fastapi import APIRouter, UploadFile, File, Form
import database

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
    return {"success": True, "product_id": pid}


@router.post("/products/delete")
async def delete_product(product_id: int = Form(...)):
    ok = database.delete_product_row(product_id)
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
    """Post a product image + caption to the configured Facebook page."""
    import config
    from pathlib import Path
    import requests as req

    if not config.facebook_enabled():
        return {"success": False, "message": "Facebook API credentials not configured."}

    contents = await image.read()
    ext = os.path.splitext(image.filename or "fb_post")[1] or ".jpg"
    save_dir = Path("uploads/facebook_posts")
    save_dir.mkdir(parents=True, exist_ok=True)
    import uuid
    image_path = save_dir / f"fb_{uuid.uuid4().hex[:8]}{ext}"
    image_path.write_bytes(contents)

    url = (
        f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}/"
        f"{config.FB_PAGE_ID}/photos"
    )
    try:
        with open(image_path, "rb") as f:
            resp = req.post(url, files={"source": f}, data={
                "caption": caption, "published": "true",
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
            }, timeout=60)

        if resp.status_code == 200:
            post_id = resp.json().get("id", "")
            return {"success": True, "post_id": post_id, "message": "Posted to Facebook!"}
        else:
            return {"success": False, "message": f"Facebook API error: {resp.text[:200]}"}
    except Exception as exc:
        return {"success": False, "message": f"Facebook post failed: {str(exc)[:200]}"}
