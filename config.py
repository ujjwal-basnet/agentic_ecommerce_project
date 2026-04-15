"""All env vars — single source of truth. Nothing else calls os.getenv()."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

DB_PATH = os.getenv("DB_PATH", "database/smartshop.db")
DB_IMAGES_DIR = os.getenv("DB_IMAGES_DIR", "database/images")
USER_IMAGES_DIR = os.getenv("USER_IMAGES_DIR", "uploads/user_images")
TRYON_DIR = os.getenv("TRYON_DIR", "uploads/tryon_outputs")

FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v24.0")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "smartshop-webhook")

# WhatsApp Business API
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "smartshop-webhook")

# Channel feature flags
ENABLE_FB_MESSENGER = os.getenv("ENABLE_FB_MESSENGER", "false").lower() == "true"
ENABLE_WHATSAPP = os.getenv("ENABLE_WHATSAPP", "false").lower() == "true"
ENABLE_VOICE = os.getenv("ENABLE_VOICE", "true").lower() == "true"

MCP_LOG_PATH = os.getenv("MCP_LOG_PATH", "logs/mcp_log.jsonl")

CUSTOMER_API_URL = os.getenv("CUSTOMER_API_URL", "http://localhost:8000")
OWNER_API_URL = os.getenv("OWNER_API_URL", "http://localhost:8000")


def openai_enabled() -> bool:
    return bool(OPENAI_API_KEY and OPENAI_API_KEY.strip())


def facebook_enabled() -> bool:
    return bool(FB_PAGE_ID and FB_PAGE_ID.strip() and FB_PAGE_ACCESS_TOKEN and FB_PAGE_ACCESS_TOKEN.strip())


def whatsapp_enabled() -> bool:
    return bool(WHATSAPP_API_TOKEN and WHATSAPP_API_TOKEN.strip() and WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_PHONE_NUMBER_ID.strip())


# Ensure directories exist
for d in [Path(DB_PATH).parent, Path(DB_IMAGES_DIR),
          Path(USER_IMAGES_DIR), Path(TRYON_DIR), Path(MCP_LOG_PATH).parent]:
    d.mkdir(parents=True, exist_ok=True)
