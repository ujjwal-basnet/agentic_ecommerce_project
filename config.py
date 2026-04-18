"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM / Google Gemini on Vertex AI ────────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION", "us-central1")
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GOOGLE_GENAI_USE_VERTEXAI = (
    _VERTEX_ENV.lower() in {"1", "true", "yes", "on"}
    if _VERTEX_ENV is not None
    else True
)

# Kept only as a fallback for Gemini Developer API code paths elsewhere.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY = GOOGLE_API_KEY  # Legacy alias for older imports/configs.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

# ── LLM / OpenRouter (commented out - switch back by changing llm.py) ────────
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
# OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
# OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", OPENROUTER_MODEL)
# OPENROUTER_REASONING_ENABLED = os.getenv("OPENROUTER_REASONING_ENABLED", "true").lower() == "true"
# OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
# OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Agentic Ecommerce")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SUPABASE_DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or ""
)
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
DB_PATH = os.getenv("DB_PATH", "data/database.sqlite")  # Legacy local path.
PRODUCTS_MD_PATH = os.getenv("PRODUCTS_MD_PATH", "data/products.md")
PRODUCT_IMAGES_DIR = os.getenv("PRODUCT_IMAGES_DIR", "data/products")
USER_UPLOADS_DIR = os.getenv("USER_UPLOADS_DIR", "data/uploads")
TRYON_DIR = os.getenv("TRYON_DIR", "data/tryon")
CAMPAIGN_DIR = os.getenv("CAMPAIGN_DIR", "data/campaigns")

# Public base URL — used by Facebook/Instagram Graph API (which fetch images by URL).
# Set this to your Render (or production) HTTPS URL.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Nano Banana / Gemini image generation.
NANO_BANANA_MODEL = os.getenv("NANO_BANANA_MODEL", GEMINI_IMAGE_MODEL)

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
GRAPH_API_BASE = f"https://graph.facebook.com/{FB_GRAPH_VERSION}"

# Instagram Business Account
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_VERIFY_TOKEN = os.getenv("IG_VERIFY_TOKEN", META_VERIFY_TOKEN)

# Auto-reply messages
DM_AUTO_REPLY = os.getenv("DM_AUTO_REPLY", "Thanks for your message! We'll get back to you soon.")
COMMENT_AUTO_REPLY = os.getenv("COMMENT_AUTO_REPLY", "Thanks for your comment! 🙌")
DM_FALLBACK_REPLY = os.getenv("DM_FALLBACK_REPLY", DM_AUTO_REPLY)
COMMENT_FALLBACK_REPLY = os.getenv("COMMENT_FALLBACK_REPLY", COMMENT_AUTO_REPLY)

# Short-name aliases for work_flow compatibility
APP_ID = META_APP_ID
APP_SECRET = META_APP_SECRET
VERIFY_TOKEN = META_VERIFY_TOKEN
ACCESS_TOKEN = META_ACCESS_TOKEN

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

# Remote MCP access for Claude/Cursor/etc. Set this on Render and keep it secret.
MCP_BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "")


def gemini_enabled() -> bool:
    if GOOGLE_GENAI_USE_VERTEXAI:
        return bool(GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS)
    return bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())




# Ensure directories exist
for d in [Path(DB_PATH).parent, Path(PRODUCT_IMAGES_DIR),
          Path(USER_UPLOADS_DIR), Path(TRYON_DIR), Path(CAMPAIGN_DIR),
          Path(PROTOCOL_LOG_PATH).parent]:
    d.mkdir(parents=True, exist_ok=True)
