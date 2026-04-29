"""REST routes for specialist agents — direct API, no protocol wrapper."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from api import db as database
from api.tools import perform_virtual_try_on
from api.schemas import TryOnResponse

router = APIRouter(prefix="/specialist", tags=["specialist"])


@router.post("/tryon", response_model=TryOnResponse)
async def tryon(
    product_id: int = Form(...),
    photo: UploadFile = File(...),
):
    """Virtual try-on: accepts product_id + user photo, returns AI-generated image."""
    contents = await photo.read()
    ext = Path(photo.filename or "photo.jpg").suffix or ".jpg"
    user_image_path = database.save_user_image(
        contents, f"specialist_tryon_{product_id}_{uuid.uuid4().hex[:8]}", ext
    )
    result = json.loads(
        perform_virtual_try_on.invoke(
            {
                "product_id": product_id,
                "user_image_path": user_image_path,
            }
        )
    )
    return result
