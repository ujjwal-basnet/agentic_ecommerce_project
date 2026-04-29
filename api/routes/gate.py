"""App-level login gate — validates username/password, returns JWT."""

from __future__ import annotations

import datetime
import logging

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Form

from api import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/gate/login")
async def gate_login(
    username: str = Form(...),
    password: str = Form(...),
):
    """Validate credentials and return a signed JWT."""
    if not config.APP_USERNAME:
        raise HTTPException(status_code=503, detail="Auth gate not configured")

    if username.strip() != config.APP_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not config.APP_PASSWORD_HASH:
        raise HTTPException(status_code=503, detail="Password hash not configured")

    if not bcrypt.checkpw(password.encode(), config.APP_PASSWORD_HASH.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {
        "sub": username.strip(),
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
    logger.info("Gate login: %s", username.strip())
    return {"ok": True, "token": token, "expires_hours": config.JWT_EXPIRY_HOURS}


@router.get("/api/gate/check")
async def gate_check():
    """Tell frontends whether the gate is enabled (credentials configured)."""
    return {"enabled": bool(config.APP_USERNAME and config.APP_PASSWORD_HASH)}
