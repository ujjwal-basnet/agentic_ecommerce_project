"""REST routes for specialist agents — direct API, no MCP."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter(prefix="/specialist", tags=["specialist"])


@router.post("/tryon")
async def tryon(
    product_id: int = Form(...),
    photo: UploadFile = File(...),
):
    """Virtual try-on: accepts product_id + user photo, returns AI-generated image."""
    from specialist_agents.tryon import try_on

    contents = await photo.read()
    result = try_on(
        product_id=product_id,
        user_image_bytes=contents,
        filename=photo.filename or "photo.jpg",
    )
    return result


@router.post("/facebook/post")
async def facebook_post(
    image: UploadFile = File(...),
    caption: str = Form(""),
):
    """Post image + caption to Facebook Page."""
    from specialist_agents.facebook import post_to_page

    contents = await image.read()
    result = post_to_page(
        image_bytes=contents,
        caption=caption,
        filename=image.filename or "post.jpg",
    )
    return result
