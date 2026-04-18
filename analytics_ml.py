"""Owner analytics ML — day-over-day sales index + linear-regression forecast.

Uses pandas + numpy + scikit-learn. 5-minute in-memory TTL cache.

Signals:
  demand = W_ORDERS * revenue
         + W_CART   * cart_adds  (scaled)
         + W_VIEWS  * views      (scaled)
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

import database

logger = logging.getLogger(__name__)

# Signal weights (orders > intent > curiosity)
W_ORDERS, W_CART, W_VIEWS = 0.6, 0.25, 0.15

_TTL_SECONDS = 300
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value) -> None:
    _cache[key] = (time.time(), value)


def invalidate_cache() -> None:
    _cache.clear()


# ── Daily signal frame ─────────────────────────────────────────────────────

def _daily_frame(days: int) -> pd.DataFrame:
    """Build a dense daily DataFrame of weighted demand ending today."""
    raw = database.get_daily_signals(days)
    end = date.today()
    start = end - timedelta(days=days - 1)
    idx = pd.date_range(start=start, end=end, freq="D")

    df = pd.DataFrame(raw)
    if df.empty:
        df = pd.DataFrame({"date": [], "revenue": [], "cart_adds": [], "views": []})
    else:
        df["date"] = pd.to_datetime(df["date"])

    df = df.set_index("date").reindex(idx).fillna(0)
    df.index.name = "date"

    df["demand"] = (
        W_ORDERS * df["revenue"]
        + W_CART * df["cart_adds"] * 100.0   # lift intent to revenue-ish scale
        + W_VIEWS * df["views"] * 20.0       # lift views more
    )
    return df


# ── Forecast via sklearn LinearRegression ──────────────────────────────────

Range = Literal["7d", "30d", "ytd"]
_RANGE_WINDOWS: dict[str, tuple[int, int]] = {"7d": (14, 7), "30d": (60, 30)}


def _forecast_window(range_: Range) -> tuple[int, int]:
    if range_ == "ytd":
        today = date.today()
        return (today - date(today.year, 1, 1)).days + 1, 30
    return _RANGE_WINDOWS[range_]


def _fit_and_forecast(df: pd.DataFrame, horizon: int) -> np.ndarray:
    """Linear regression on day-index → demand. Returns `horizon` future points."""
    if df.empty or df["demand"].sum() == 0:
        return np.zeros(horizon)

    X = np.arange(len(df)).reshape(-1, 1)
    y = df["demand"].to_numpy()

    model = LinearRegression().fit(X, y)
    X_future = np.arange(len(df), len(df) + horizon).reshape(-1, 1)
    preds = model.predict(X_future)
    return np.clip(preds, 0.0, None)


def forecast_revenue(range_: Range = "7d") -> dict:
    cache_key = f"forecast::{range_}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    hist_days, fwd_days = _forecast_window(range_)
    df = _daily_frame(hist_days)
    future = _fit_and_forecast(df, fwd_days)

    hist_points = [
        {"date": idx.date().isoformat(), "value": round(float(v), 2), "is_forecast": False}
        for idx, v in df["demand"].items()
    ]
    last_date = df.index[-1].date() if len(df) else date.today()
    fwd_points = [
        {
            "date": (last_date + timedelta(days=i + 1)).isoformat(),
            "value": round(float(v), 2),
            "is_forecast": True,
        }
        for i, v in enumerate(future)
    ]

    result = {
        "range": range_,
        "points": hist_points + fwd_points,
        "historical_end_index": len(hist_points) - 1,
    }
    _cache_set(cache_key, result)
    return result


# ── AI Sales Index = day-over-day revenue delta % ──────────────────────────

def sales_day_delta() -> dict:
    """Today's revenue vs yesterday's — as a simple percentage."""
    cache_key = "sales_day_delta"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    today_rev = float(database.get_revenue_for_day(0))
    yday_rev = float(database.get_revenue_for_day(1))

    if yday_rev > 0:
        delta = (today_rev - yday_rev) / yday_rev * 100.0
    elif today_rev > 0:
        delta = 100.0
    else:
        delta = 0.0

    result = {
        "today_revenue": round(today_rev, 2),
        "yesterday_revenue": round(yday_rev, 2),
        "day_delta_pct": round(delta, 1),
    }
    _cache_set(cache_key, result)
    return result


# ── Trending products (top 3 by weighted signals) ──────────────────────────

def trending_products(limit: int = 3) -> list[dict]:
    cache_key = f"trending::{limit}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    rows = database.get_product_signals(days=30)
    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["score"] = (
        W_ORDERS * df["orders_units"].astype(float)
        + W_CART * df["cart_adds"].astype(float)
        + W_VIEWS * df["views"].astype(float)
    )
    df = df.sort_values("score", ascending=False).head(limit)
    if df.empty:
        return []

    max_score = float(df["score"].max()) or 1.0
    out: list[dict] = []
    for rank, (_, r) in enumerate(df.iterrows()):
        pct = int(round((float(r["score"]) / max_score) * 100))
        if rank == 0 and r["score"] > 0:
            level = "Peak"
        elif pct >= 60:
            level = "High"
        else:
            level = "Med"
        out.append({
            "product_id": int(r["product_id"]),
            "name": str(r["name"]),
            "price": float(r["price"]),
            "image_path": r.get("image_path") or None,
            "score": round(float(r["score"]), 2),
            "demand_pct": max(8, min(100, pct)),
            "demand_level": level,
        })

    _cache_set(cache_key, out)
    return out
