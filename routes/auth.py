"""Customer auth — simple name+email login bound to a session."""

from __future__ import annotations
import re

from fastapi import APIRouter, Form, HTTPException

import database
from schemas import LoginResponse, MeResponse

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(
    name: str = Form(...),
    email: str = Form(...),
    session_id: str = Form(...),
):
    name = name.strip()
    email = email.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="invalid email")

    user = database.upsert_user(name, email)
    if not user:
        raise HTTPException(status_code=500, detail="failed to create user")
    database.bind_session_user(session_id, user["id"])
    return {"ok": True, "user": user}


@router.get("/api/auth/me", response_model=MeResponse)
async def me(session_id: str):
    user = database.get_user_by_session(session_id)
    return {"user": user}


@router.post("/api/auth/logout")
async def logout(session_id: str = Form(...)):
    database.unbind_session_user(session_id)
    return {"ok": True}
