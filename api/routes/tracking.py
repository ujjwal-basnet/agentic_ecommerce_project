"""Customer behavior tracking — product views feed the demand forecaster."""

from __future__ import annotations

from fastapi import APIRouter, Form

from api import db as database
from api.analytics import forecast as analytics_ml
from api.schemas import TrackViewResponse

router = APIRouter()


@router.post("/api/track/view", response_model=TrackViewResponse)
async def track_view(
    session_id: str = Form(...),
    product_id: int = Form(...),
    search_query: str | None = Form(None),
):
    database.log_product_view(session_id, product_id, search_query)
    analytics_ml.invalidate_cache()
    return {"ok": True}
