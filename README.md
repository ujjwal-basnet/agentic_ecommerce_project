# SmartShop E-commerce Chatbot

AI-powered e-commerce chatbot with multi-channel support (Web, Instagram, Facebook, MCP).

## Branches

| Branch | Purpose | Status |
|--------|---------|--------|
| `master` | Production stable | Legacy |
| `real-mcp` | MCP server implementation | Previous working branch |
| `migrate-superbase` | **Current** - Supabase PostgreSQL migration | Active development |
| `schemas_version` | Schema definitions | Feature branch |

## Current Branch: `migrate-superbase`

This branch migrates from SQLite to Supabase PostgreSQL:
- Connection pooling (ThreadedConnectionPool)
- In-memory product caching
- Google Vertex AI integration (google_client.py)
- Clean config (removed dead vars)

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
cp .env.example .env  # Fill in your credentials
python main.py
```

## Environment Variables

Required in `.env`:
```bash
# Database
DATABASE_URL=postgresql://...

# Google/Vertex AI
GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json
GOOGLE_CLOUD_PROJECT=your-project

# Meta (Instagram/Facebook)
META_ACCESS_TOKEN=...
IG_USER_ID=...
```

## Architecture

```
User Message → Planner → Executor (Tools) → Response Generator → Text/UI
                                    ↓
                              Supabase PostgreSQL
```
