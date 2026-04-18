"""Owner dashboard API routes — analytics, products CRUD, facebook, campaign workflow."""

from __future__ import annotations
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

import analytics_ml
import config
import database
import llm
from schemas import (
    CaptionRestyleResponse,
    LaunchCampaignResponse,
    LogisticsResponse,
    OwnerAnalyticsResponse,
    OverviewResponse,
    ProductCreateResponse,
    ProductDeleteResponse,
    ProductSchema,
    ProductUpdateResponse,
    SocialPostResponse,
    StatusUpdateResponse,
    ForecastResponse,
    TrendingResponse,
    VisualGenerateResponse,
)

_log = logging.getLogger("smartshop.owner")

router = APIRouter(prefix="/owner")


# ── Analytics (Lumière Noir dashboard) ─────────────────────────────────────

_FORECAST_RANGES = {"7d", "30d", "ytd"}


def _overview_stats() -> dict:
    stats = database.get_summary_stats()
    day = analytics_ml.sales_day_delta()
    return {
        "total_revenue": stats["total_revenue"],
        "total_orders": stats["total_orders"],
        "total_customers": database.get_customer_count(),
        "total_products": stats["total_products"],
        "today_revenue": day["today_revenue"],
        "yesterday_revenue": day["yesterday_revenue"],
        "day_delta_pct": day["day_delta_pct"],
    }


def _valid_range(range_: str) -> str:
    if range_ not in _FORECAST_RANGES:
        raise HTTPException(status_code=400, detail="range must be 7d, 30d, or ytd")
    return range_


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _logistics_rows(limit: int) -> list[dict]:
    return [
        {**row, "user_initials": _initials(row.get("user_name", ""))}
        for row in database.get_logistics_rows(limit)
    ]


@router.get("/analytics", response_model=OwnerAnalyticsResponse)
async def analytics_dashboard(
    range: str = "7d",
    trend_limit: int = 3,
    logistics_limit: int = 20,
):
    range_ = _valid_range(range)
    return {
        "stats": _overview_stats(),
        "forecast": analytics_ml.forecast_revenue(range_),
        "products": analytics_ml.trending_products(limit=trend_limit),
        "rows": _logistics_rows(logistics_limit),
    }


@router.get("/analytics/overview", response_model=OverviewResponse)
async def analytics_overview():
    return {"stats": _overview_stats()}


@router.get("/analytics/forecast", response_model=ForecastResponse)
async def analytics_forecast(range: str = "7d"):
    return analytics_ml.forecast_revenue(_valid_range(range))


@router.get("/analytics/trending", response_model=TrendingResponse)
async def analytics_trending(limit: int = 3):
    return {"products": analytics_ml.trending_products(limit=limit)}


@router.get("/analytics/logistics", response_model=LogisticsResponse)
async def analytics_logistics(limit: int = 20):
    return {"rows": _logistics_rows(limit)}


@router.post("/orders/status", response_model=StatusUpdateResponse)
async def update_order_status(
    order_id: int = Form(...),
    status: str = Form(...),
):
    try:
        ok = database.update_order_status(order_id, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="order not found")
    analytics_ml.invalidate_cache()
    return {"ok": True, "order_id": order_id, "status": status}


# ── Campaign workflow (Curator AI) ─────────────────────────────────────────

_TONE_DIRECTIVES = {
    "punchy": "Short, urgent, high-energy. One or two sentences. 1-3 emojis. Drive click-through.",
    "editorial": "Elevated, magazine-style voice. Confident and concise. No emojis. 2-3 sentences.",
    "technical": "Feature-first. Lead with the spec or material benefit. Minimal hype.",
}


_LANGUAGE_DIRECTIVES = {
    "en": "Write the caption in natural English.",
    "ne": (
        "Write the caption in natural Nepali using Devanagari script (नेपाली). "
        "Keep product name, price numerals, and hashtags as-is in English. "
        "The body text must be Nepali, not romanized."
    ),
}


@router.post("/campaign/caption/restyle", response_model=CaptionRestyleResponse)
async def campaign_caption_restyle(
    product_id: int = Form(...),
    tone: str = Form("editorial"),
    language: str = Form("en"),
):
    """Ask the LLM to rewrite a social caption for the given product in the chosen tone + language."""
    tone_key = (tone or "editorial").lower().strip()
    lang_key = (language or "en").lower().strip()
    directive = _TONE_DIRECTIVES.get(tone_key, _TONE_DIRECTIVES["editorial"])
    lang_directive = _LANGUAGE_DIRECTIVES.get(lang_key, _LANGUAGE_DIRECTIVES["en"])

    product = database.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    system = (
        "You are a social-media copywriter for a high-end e-commerce brand. "
        "Produce only the caption text — no preamble, no quotes, no explanations."
    )
    user = (
        f"Tone: {tone_key}. Style: {directive}\n"
        f"Language: {lang_directive}\n\n"
        f"Product: {product.get('name', '')}\n"
        f"Category: {product.get('category', '')}\n"
        f"Color: {product.get('color', '')}\n"
        f"Price: Rs. {product.get('price', 0)}\n"
        f"Description: {product.get('description', '') or 'n/a'}\n\n"
        "Write a ready-to-post Instagram / Facebook caption. Include 2-4 relevant hashtags "
        "at the end. Do not exceed 280 characters."
    )
    try:
        caption = (await llm.acall_llm(system, user)).strip()
    except Exception:
        _log.exception("campaign_caption_restyle failed")
        raise HTTPException(status_code=502, detail="LLM call failed")

    return {"caption": caption, "tone": tone_key, "language": lang_key}


_BACKGROUND_PRESETS = {
    "studio_white": "Clean seamless white studio cyclorama background with soft diffused lighting, minimal shadow underneath the subject.",
    "studio_noir": "Deep matte charcoal studio background with dramatic single-source side lighting and rich shadow detail.",
    "soft_peach": "Warm peach-to-blush gradient studio backdrop with gentle golden-hour lighting and subtle film grain.",
    "concrete": "Minimalist brutalist polished concrete wall backdrop, cool daylight, hard editorial shadows.",
    "coastal_blue": "Soft misty coastal blue gradient backdrop with diffused overcast light, calm atmosphere.",
    "warm_taupe": "Neutral taupe seamless backdrop with warm tungsten key light and a soft rim light.",
}


@router.post("/campaign/visual/generate", response_model=VisualGenerateResponse)
async def campaign_visual_generate(
    product_id: int = Form(...),
    prompt: str = Form(""),
    background_preset: str = Form(""),
    model_photo: UploadFile | None = File(None),
    background_photo: UploadFile | None = File(None),
):
    """Generate a campaign image from product + optional model + optional background + prompt.

    Background can come from an uploaded photo OR a named preset. Uploaded photo wins
    if both are supplied.
    """
    from campaign_visual import generate_campaign_image

    product = database.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product_image_path = product.get("image_path") or ""
    if not product_image_path or (
        not product_image_path.startswith("http")
        and not Path(product_image_path).exists()
    ):
        raise HTTPException(status_code=400, detail=f"Product {product_id} has no usable image")

    model_image_path: str | None = None
    if model_photo is not None and model_photo.filename:
        contents = await model_photo.read()
        ext = Path(model_photo.filename).suffix or ".jpg"
        model_image_path = database.save_user_image(
            contents, f"campaign_model_{product_id}_{uuid.uuid4().hex[:8]}", ext
        )

    background_image_path: str | None = None
    if background_photo is not None and background_photo.filename:
        contents = await background_photo.read()
        ext = Path(background_photo.filename).suffix or ".jpg"
        background_image_path = database.save_user_image(
            contents, f"campaign_bg_{product_id}_{uuid.uuid4().hex[:8]}", ext
        )

    effective_prompt = prompt or ""
    preset_key = (background_preset or "").strip().lower()
    if preset_key and preset_key in _BACKGROUND_PRESETS and background_image_path is None:
        snippet = _BACKGROUND_PRESETS[preset_key]
        effective_prompt = f"{effective_prompt} Background: {snippet}".strip()

    try:
        out_path = generate_campaign_image(
            product_image_path,
            model_image_path,
            effective_prompt,
            background_image_path=background_image_path,
        )
    except Exception as e:
        _log.exception("campaign_visual_generate failed")
        return {"success": False, "error": str(e)}

    if out_path.startswith("http://") or out_path.startswith("https://"):
        return {"success": True, "image_path": out_path, "image_url": out_path}
    rel = Path(out_path).name
    return {"success": True, "image_path": out_path, "image_url": f"/data/campaigns/{rel}"}


@router.post("/campaign/launch", response_model=LaunchCampaignResponse)
async def campaign_launch(
    image_path: str = Form(...),
    caption: str = Form(""),
    channels: str = Form("facebook"),  # comma-separated: "facebook,instagram"
):
    """Deploy the generated visual + caption to selected channels."""
    from routes.facebook import post_photo_to_page
    from routes.instagram import publish_photo_to_instagram

    if image_path.startswith("http://") or image_path.startswith("https://"):
        image_url = image_path
    else:
        p = Path(image_path)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"image_path not found: {image_path}")
        base = config.PUBLIC_BASE_URL
        if not base:
            raise HTTPException(
                status_code=400,
                detail="PUBLIC_BASE_URL not configured. Set it to your Render (or production) HTTPS URL so Facebook/Instagram can fetch the image.",
            )
        image_url = f"{base}/data/campaigns/{p.name}"

    wanted = [c.strip().lower() for c in channels.split(",") if c.strip()]
    deployed: list[str] = []
    failed: list[dict] = []

    if "facebook" in wanted:
        try:
            await post_photo_to_page(image_url, caption)
            deployed.append("facebook")
        except Exception as e:
            _log.exception("facebook launch failed")
            failed.append({"channel": "facebook", "error": str(e)})

    if "instagram" in wanted:
        try:
            await publish_photo_to_instagram(image_url, caption)
            deployed.append("instagram")
        except Exception as e:
            _log.exception("instagram launch failed")
            failed.append({"channel": "instagram", "error": str(e)})

    return {"ok": len(deployed) > 0 and not failed, "deployed": deployed, "failed": failed}


# ── Products CRUD ──────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductSchema])
async def list_products():
    return database.get_all_products()


@router.post("/products/new", response_model=ProductCreateResponse)
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
    analytics_ml.invalidate_cache()
    return {"success": True, "product_id": pid}


@router.post("/products/delete", response_model=ProductDeleteResponse)
async def delete_product(product_id: int = Form(...)):
    ok = database.delete_product_row(product_id)
    analytics_ml.invalidate_cache()
    return {"ok": ok}


@router.post("/products/update", response_model=ProductUpdateResponse)
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
        analytics_ml.invalidate_cache()
    return {"success": True}


@router.post("/facebook/post", response_model=SocialPostResponse)
async def post_to_facebook(
    image: UploadFile = File(...),
    caption: str = Form(""),
):
    """Post a product image + caption — delegates to specialist agent."""
    raise RuntimeError("Facebook image upload posting is not wired. Use /api/facebook/post with image_url.")
