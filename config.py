"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM / Google Gemini on Vertex AI ────────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GOOGLE_GENAI_USE_VERTEXAI = (
    _VERTEX_ENV.lower() in {"1", "true", "yes", "on"}
    if _VERTEX_ENV is not None
    else True
)

# Kept only as a fallback for Gemini Developer API code paths elsewhere.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
PRODUCTS_MD_PATH = os.getenv("PRODUCTS_MD_PATH", "products.md")
PRODUCT_IMAGES_DIR = os.getenv("PRODUCT_IMAGES_DIR", "data/products")
USER_UPLOADS_DIR = os.getenv("USER_UPLOADS_DIR", "data/uploads")
TRYON_DIR = os.getenv("TRYON_DIR", "data/tryon")
CAMPAIGN_DIR = os.getenv("CAMPAIGN_DIR", "data/campaigns")

# Public base URL — used by Facebook/Instagram Graph API (which fetch images by URL).
# Set this to your Render (or production) HTTPS URL.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Supabase Storage — for persisting product images, uploads, try-on results, campaigns.
# SUPABASE_URL: your project URL e.g. https://xyzxyz.supabase.co
# SUPABASE_SERVICE_KEY: service_role key (Settings → API → service_role secret)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Meta/Facebook/Instagram Unified Config ───────────────────────────────────
# App credentials (shared across Facebook, Instagram, WhatsApp)
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "smartshop-webhook")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

# Facebook Page
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN") or META_ACCESS_TOKEN
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v24.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{FB_GRAPH_VERSION}"

# Instagram Business account
IG_USER_ID = os.getenv("IG_USER_ID", "")

PROTOCOL_LOG_PATH = os.getenv("PROTOCOL_LOG_PATH", "logs/protocol_log.jsonl")

# Remote MCP access for Claude/Cursor/etc. Set this on Render and keep it secret.
MCP_BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "")


def gemini_enabled() -> bool:
    if GOOGLE_GENAI_USE_VERTEXAI:
        return bool(GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS)
    return bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())




# Ensure directories exist
for d in [Path(PRODUCT_IMAGES_DIR), Path(USER_UPLOADS_DIR),
          Path(TRYON_DIR), Path(CAMPAIGN_DIR),
          Path(PROTOCOL_LOG_PATH).parent]:
    d.mkdir(parents=True, exist_ok=True)
