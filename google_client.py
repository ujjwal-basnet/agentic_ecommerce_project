"""Shared Google/Gemini clients — created once per process, reused everywhere.

Two singletons:
- get_chat_model()    → ChatVertexAI for LLM calls (llm.py)
- get_genai_client()  → genai.Client for image generation (try-on, campaigns)

Both pick credentials from GOOGLE_APPLICATION_CREDENTIALS via Application Default
Credentials — no manual service_account loading. Set GOOGLE_GENAI_USE_VERTEXAI=false
in .env to fall back to plain API key mode (dev/testing).
"""

from __future__ import annotations

import os
from pathlib import Path

import config

_chat_model = None
_genai_client = None


def _ensure_adc() -> None:
    """Make sure Application Default Credentials can find the service account."""
    if config.GOOGLE_APPLICATION_CREDENTIALS:
        creds_path = str(Path(config.GOOGLE_APPLICATION_CREDENTIALS).expanduser())
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds_path)


def get_chat_model():
    """Singleton chat model. Vertex mode uses ADC automatically."""
    global _chat_model
    if _chat_model is not None:
        return _chat_model

    from langchain_google_genai import ChatGoogleGenerativeAI

    if config.GOOGLE_GENAI_USE_VERTEXAI:
        _ensure_adc()
        _chat_model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION,
            temperature=0.2,
        )
    else:
        _chat_model = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            api_key=config.GOOGLE_API_KEY,
            temperature=0.2,
        )
    return _chat_model


def get_genai_client():
    """Singleton google.genai.Client for image generation."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    from google import genai

    if config.GOOGLE_GENAI_USE_VERTEXAI:
        _ensure_adc()
        _genai_client = genai.Client(
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION,
        )
    else:
        _genai_client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _genai_client
