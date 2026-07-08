"""REST routes for specialist agents — direct API, no protocol wrapper."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from api import db as database
from api.agents.tryon_agent import tryon_impl
from api.image_backends import IMAGE_MODELS
from api.schemas import TryOnResponse

router = APIRouter(prefix="/specialist", tags=["specialist"])


@router.post("/tryon", response_model=TryOnResponse)
async def tryon(
    product_id: int = Form(...),
    photo: UploadFile = File(...),
    model: str = Form("nano_banana"),
):
    """Virtual try-on: accepts product_id + user photo + model selection, returns AI-generated image."""
    contents = await photo.read()
    ext = Path(photo.filename or "photo.jpg").suffix or ".jpg"
    user_image_path = database.save_user_image(
        contents, f"specialist_tryon_{product_id}_{uuid.uuid4().hex[:8]}", ext
    )
    result = await tryon_impl(
        {
            "product_id": product_id,
            "user_image_path": user_image_path,
            "model": model,
        }
    )
    return result


@router.get("/image-models")
async def list_image_models():
    """Return the list of available image generation models for frontend dropdowns."""
    return {"models": list(IMAGE_MODELS.values())}
