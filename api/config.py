"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Critical: disable Vertex AI mode for google-genai SDK ────────────────────
# The system shell may export GOOGLE_GENAI_USE_VERTEXAI=true, which redirects
# all google-genai calls to aiplatform.googleapis.com (requires OAuth2, not
# an API key). Forcibly disable it so we always use generativelanguage.googleapis.com.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

# ── LLM / OpenAI (pydantic-ai) ───────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8002/v1")

# Intent routing: when true, an LLM classifies each turn's intent (generalizes
# to any phrasing — "how r u", "wassup", etc.). Falls back to the embedding
# router automatically if the LLM is unreachable. Set false for fully offline dev.
ROUTER_USE_LLM = os.getenv("ROUTER_USE_LLM", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL") or "http://localhost:8002/v1"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")


# ── Vector Search / Pinecone (uses integrated llama-text-embed-v2) ──────────
# Accept both upper and lower case for convenience — some .env files have
# lower case keys (pinecone_api_key, index_name).
PINECONE_API_KEY = (
    os.getenv("PINECONE_API_KEY")
    or os.getenv("pinecone_api_key")
    or ""
)
PINECONE_INDEX_NAME = (
    os.getenv("PINECONE_INDEX_NAME")
    or os.getenv("index_name")
    or "ecommerce"
)
# Pinecone namespace — keep "__default__" to match the UI default view.
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "__default__")
PINECONE_MEME_NAMESPACE = os.getenv("PINECONE_MEME_NAMESPACE", "meme_assets")

# ── LLM / Google Gemini (image generation only, NO Vertex AI) ───────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_API_KEY_2 = os.getenv("GOOGLE_API_KEY_2", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp")

# ── Groq (fast rewriter) ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API") or os.getenv("GROQ_API_KEY") or ""
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ── RunPod (FLUX.1 Kontext — try-on & campaign image editing) ──────────────
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY") or os.getenv("RUNPOD_API") or ""
RUNPOD_FLUX_KONTEXT_ENDPOINT = "black-forest-labs-flux-1-kontext-dev"

# ── Runflow (Nano Banana 2 — FREE $10 credit for image editing) ────────────
RUNFLOW_API_KEY = os.getenv("RUNFLOW_API_KEY") or ""

# ── Pollinations.ai ─────────────────────────────────────────────────────────
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
PRODUCTS_MD_PATH = os.getenv("PRODUCTS_MD_PATH", "data/products.md")
PRODUCT_IMAGES_DIR = os.getenv("PRODUCT_IMAGES_DIR", "data/products")
USER_UPLOADS_DIR = os.getenv("USER_UPLOADS_DIR", "data/uploads")
TRYON_DIR = os.getenv("TRYON_DIR", "data/tryon")
CAMPAIGN_DIR = os.getenv("CAMPAIGN_DIR", "data/campaigns")
MEME_ASSETS_DIR = os.getenv("MEME_ASSETS_DIR", "data/memes")
MEME_RAG_SOURCE_DIR = os.getenv("MEME_RAG_SOURCE_DIR", "/home/ujjwal/meme_rag")
MEME_SUPABASE_BUCKET = os.getenv("MEME_SUPABASE_BUCKET", "meme-assets")
MEME_RAG_ENABLED = os.getenv("MEME_RAG_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEME_RAG_MIN_SCORE = float(os.getenv("MEME_RAG_MIN_SCORE", "0.10"))

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
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN") or META_ACCESS_TOKEN
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v24.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{FB_GRAPH_VERSION}"

IG_USER_ID = os.getenv("IG_USER_ID", "")

PROTOCOL_LOG_PATH = os.getenv("PROTOCOL_LOG_PATH", "logs/protocol_log.jsonl")

# ── App-level auth gate ──────────────────────────────────────────────────
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


# Ensure directories exist
for d in [
    Path(PRODUCT_IMAGES_DIR),
    Path(USER_UPLOADS_DIR),
    Path(TRYON_DIR),
    Path(CAMPAIGN_DIR),
    Path(MEME_ASSETS_DIR),
    Path(PROTOCOL_LOG_PATH).parent,
]:
    d.mkdir(parents=True, exist_ok=True)


# ── Pydantic Logfire observability ───────────────────────────────────────────
LOGFIRE_TOKEN = (
    os.getenv("LOGFIRE_TOKEN")
    or os.getenv("logfire_api")
    or ""
)

# ── Rate limiting ────────────────────────────────────────────────────────
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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


def validate() -> list[str]:
    errors: list[str] = []
    if APP_USERNAME and JWT_SECRET == _JWT_SECRET_DEFAULT:
        errors.append(
            "JWT_SECRET is set to the default placeholder. "
            'Generate a strong secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`'
        )
    if APP_USERNAME and not APP_PASSWORD_HASH:
        errors.append("APP_USERNAME set but APP_PASSWORD_HASH missing.")
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is missing — required for cloud OpenAI calls.")
    return errors


def enforce() -> None:
    errs = validate()
    if errs:
        raise RuntimeError("Config errors:\n  - " + "\n  - ".join(errs))
