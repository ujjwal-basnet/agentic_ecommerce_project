"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM / Google Gemini ──────────────────────────────────────────────────────
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GOOGLE_GENAI_USE_VERTEXAI = (
    _VERTEX_ENV.lower() in {"1", "true", "yes", "on"}
    if _VERTEX_ENV is not None
    else True
)

# Fallback for Gemini Developer API (set GOOGLE_GENAI_USE_VERTEXAI=false to use this).
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
PRODUCTS_MD_PATH = os.getenv("PRODUCTS_MD_PATH", "data/products.md")
PRODUCT_IMAGES_DIR = os.getenv("PRODUCT_IMAGES_DIR", "data/products")
USER_UPLOADS_DIR = os.getenv("USER_UPLOADS_DIR", "data/uploads")
TRYON_DIR = os.getenv("TRYON_DIR", "data/tryon")
CAMPAIGN_DIR = os.getenv("CAMPAIGN_DIR", "data/campaigns")

# Public base URL — used by Facebook/Instagram Graph API (which fetch images by URL).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Supabase Storage — product images, uploads, try-on results, campaigns.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Meta/Facebook/Instagram ───────────────────────────────────────────────────
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "smartshop-webhook")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
# FB_PAGE_ACCESS_TOKEN takes priority for all Page + IG Graph API calls.
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN") or META_ACCESS_TOKEN
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v24.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{FB_GRAPH_VERSION}"

IG_USER_ID = os.getenv("IG_USER_ID", "")

PROTOCOL_LOG_PATH = os.getenv("PROTOCOL_LOG_PATH", "logs/protocol_log.jsonl")

# ── App-level auth gate ──────────────────────────────────────────────────
# Protects all API routes so only approved users burn your API credits.
# Generate hash: python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH", "")
_JWT_SECRET_DEFAULT = "change-me-before-deploy"
JWT_SECRET = os.getenv("JWT_SECRET", _JWT_SECRET_DEFAULT)
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "72"))

# Remote MCP access for Claude/Cursor/etc.
MCP_BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "")
MCP_PUBLIC = os.getenv("MCP_PUBLIC", "false").lower() in {"1", "true", "yes", "on"}

# ── Email receipts (SMTP) ────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")


def gemini_enabled() -> bool:
    if GOOGLE_GENAI_USE_VERTEXAI:
        return bool(GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS)
    return bool(GOOGLE_API_KEY and GOOGLE_API_KEY.strip())


# Ensure directories exist
for d in [
    Path(PRODUCT_IMAGES_DIR),
    Path(USER_UPLOADS_DIR),
    Path(TRYON_DIR),
    Path(CAMPAIGN_DIR),
    Path(PROTOCOL_LOG_PATH).parent,
]:
    d.mkdir(parents=True, exist_ok=True)


# ── Rate limiting ────────────────────────────────────────────────────────
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
# default per-key limits (requests per window seconds)
RATE_LIMIT_DEFAULT = (
    int(os.getenv("RATE_LIMIT_DEFAULT_REQ", "60")),
    int(os.getenv("RATE_LIMIT_DEFAULT_WINDOW", "60")),
)
RATE_LIMIT_CHAT = (
    int(os.getenv("RATE_LIMIT_CHAT_REQ", "20")),
    int(os.getenv("RATE_LIMIT_CHAT_WINDOW", "60")),
)
RATE_LIMIT_HEAVY = (
    int(os.getenv("RATE_LIMIT_HEAVY_REQ", "5")),
    int(os.getenv("RATE_LIMIT_HEAVY_WINDOW", "60")),
)


# ── Startup validation ───────────────────────────────────────────────────
def validate() -> list[str]:
    """Return list of fatal config problems. Empty list = OK."""
    errors: list[str] = []
    # If app gate is enabled (production), JWT_SECRET MUST be changed.
    if APP_USERNAME and JWT_SECRET == _JWT_SECRET_DEFAULT:
        errors.append(
            "JWT_SECRET is set to the default placeholder. "
            'Generate a strong secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`'
        )
    if APP_USERNAME and not APP_PASSWORD_HASH:
        errors.append("APP_USERNAME set but APP_PASSWORD_HASH missing.")
    return errors


def enforce() -> None:
    """Raise RuntimeError on any fatal config problems."""
    errs = validate()
    if errs:
        raise RuntimeError("Config errors:\n  - " + "\n  - ".join(errs))
