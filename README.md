# SmartShop

Agentic ecommerce app:

- `api/` FastAPI backend
- `apps/customer/` customer chat storefront
- `apps/owner/` owner inventory, analytics, and campaign dashboard
- Supabase Postgres for data
- Supabase Storage for uploads/campaign images

## Local Run

Backend:

```bash
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Customer frontend:

```bash
npm --prefix apps/customer run dev
```

Owner frontend:

```bash
npm --prefix apps/owner run dev
```

URLs:

- Backend: `http://127.0.0.1:8000`
- Customer: `http://localhost:3000`
- Owner: `http://localhost:3001`

## Required Environment

Copy `.env.example` to `.env` locally. In production, set these in Render:

- `DATABASE_URL`
- `DB_SSLMODE=require`
- `GOOGLE_API_KEY`
- `GOOGLE_GENAI_USE_VERTEXAI=false`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `APP_USERNAME`
- `APP_PASSWORD_HASH`
- `JWT_SECRET`
- `PUBLIC_BASE_URL`

For Facebook/Instagram campaign launch:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_VERIFY_TOKEN`
- `META_ACCESS_TOKEN`
- `FB_PAGE_ID`
- `FB_PAGE_ACCESS_TOKEN`
- `IG_USER_ID`

## Render Deploy

The backend is defined in `render.yaml`.

Backend start command:

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Deploy the two Next.js apps separately:

Customer:

```text
Root Directory: apps/customer
Build Command: npm install && npm run build
Start Command: npm run start
```

Owner:

```text
Root Directory: apps/owner
Build Command: npm install && npm run build
Start Command: npm run start
```

Set this in both frontend services:

```env
NEXT_PUBLIC_API_URL=https://your-render-api.onrender.com
```

## Database

This project uses PostgreSQL through Supabase:

```env
DATABASE_URL=postgresql://...
```

Schema bootstrap currently runs in the backend on startup. Add Alembic later only when schema changes become frequent enough to need migration history.
