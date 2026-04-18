import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ── Meta App Credentials ──────────────────────────────────────────────────────
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "adadadas")

# ── Account IDs ───────────────────────────────────────────────────────────────
IG_USER_ID = os.getenv("IG_USER_ID", "")   # Instagram Business Account (@ultopalto.ai)
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")   # Facebook Page (Ecom agent)

# ── Access Token ──────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")

# ── Fallback replies (used only when the LLM call fails) ──────────────────────
DM_FALLBACK_REPLY = os.getenv("DM_FALLBACK_REPLY", "Sorry, I hit a snag. Please try again in a moment.")
COMMENT_FALLBACK_REPLY = os.getenv("COMMENT_FALLBACK_REPLY", "Thanks for reaching out! We'll follow up shortly.")

# ── Ngrok ─────────────────────────────────────────────────────────────────────
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "")
NGROK_API_URL = "http://localhost:4040/api/tunnels"

# ── Meta Graph API ────────────────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
