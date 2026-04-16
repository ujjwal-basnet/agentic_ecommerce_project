"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM / Google Gemini ─────────────────────────────────────────────────────
# Using Google Gemini API (fast, free tier available). Get key from aistudio.google.com
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY = GOOGLE_API_KEY  # Legacy alias for older imports/configs.
GEMINI_MODEL = "gemini-3-flash-preview"  # Chat/planning
GEMINI_IMAGE_MODEL = "gemini-3-flash-preview"  # Image generation/editing
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GOOGLE_GENAI_USE_VERTEXAI = (
    _VERTEX_ENV.lower() in {"1", "true", "yes", "on"} if _VERTEX_ENV is not None else None
)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# ── LLM / OpenRouter (commented out - switch back by changing llm.py) ────────
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
# OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
# OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", OPENROUTER_MODEL)
# OPENROUTER_REASONING_ENABLED = os.getenv("OPENROUTER_REASONING_ENABLED", "true").lower() == "true"
# OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
# OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Agentic Ecommerce")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

DB_PATH = os.getenv("DB_PATH", "data/database.sqlite")
PRODUCT_IMAGES_DIR = os.getenv("PRODUCT_IMAGES_DIR", "data/products")
USER_UPLOADS_DIR = os.getenv("USER_UPLOADS_DIR", "data/uploads")
TRYON_DIR = os.getenv("TRYON_DIR", "data/tryon")

# Nano Banana for fast virtual try-on (Gemini image generation)
# Docs: https://nanobananaapi.ai/
NANO_BANANA_MODEL = "gemini-2.0-flash-exp-image-generation"

# ── Meta/Facebook/Instagram Unified Config ───────────────────────────────────
# App Credentials (shared across Facebook, Instagram, WhatsApp)
META_APP_ID = os.getenv("META_APP_ID") or os.getenv("APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET") or os.getenv("APP_SECRET", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN", "smartshop-webhook")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN", "")

# Facebook Page
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN") or META_ACCESS_TOKEN
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v24.0")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", META_VERIFY_TOKEN)

# Instagram Business Account
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_VERIFY_TOKEN = os.getenv("IG_VERIFY_TOKEN", META_VERIFY_TOKEN)

# Auto-reply messages
DM_AUTO_REPLY = os.getenv("DM_AUTO_REPLY", "Thanks for your message! We'll get back to you soon.")
COMMENT_AUTO_REPLY = os.getenv("COMMENT_AUTO_REPLY", "Thanks for your comment! 🙌")

# WhatsApp Business API
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", META_VERIFY_TOKEN)

# Channel feature flags
ENABLE_FB_MESSENGER = os.getenv("ENABLE_FB_MESSENGER", "false").lower() == "true"
ENABLE_INSTAGRAM = os.getenv("ENABLE_INSTAGRAM", "false").lower() == "true"
ENABLE_WHATSAPP = os.getenv("ENABLE_WHATSAPP", "false").lower() == "true"

PROTOCOL_LOG_PATH = os.getenv("PROTOCOL_LOG_PATH", "logs/protocol_log.jsonl")

CUSTOMER_API_URL = os.getenv("CUSTOMER_API_URL", "http://localhost:8000")
OWNER_API_URL = os.getenv("OWNER_API_URL", "http://localhost:8000")


def gemini_enabled() -> bool:
    if GOOGLE_GENAI_USE_VERTEXAI:
        return True
    return bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())




# Ensure directories exist
for d in [Path(DB_PATH).parent, Path(PRODUCT_IMAGES_DIR),
          Path(USER_UPLOADS_DIR), Path(TRYON_DIR), Path(PROTOCOL_LOG_PATH).parent]:
    d.mkdir(parents=True, exist_ok=True)
