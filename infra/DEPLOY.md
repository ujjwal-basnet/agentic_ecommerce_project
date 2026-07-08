# SmartShop — Showcase Deployment

Backend + Postgres on a **DigitalOcean droplet**, LLM on **RunPod** (Lightning+ngrok
fallback), frontends on **Vercel**. DB is local to the droplet (Supabase kept as a
manual fallback). Pinecone stays as-is (recs + memes only; core search is Postgres FTS).

```
Browser → Frontend (Vercel) → Backend (droplet, HTTPS via Caddy)
                                 ├─→ Postgres (droplet volume)   [fallback: Supabase]
                                 ├─→ Pinecone (recs + memes)
                                 └─→ RunPod vLLM (Qwen3-8B-AWQ)  [fallback: Lightning+ngrok]
```

## 1. GPU — RunPod (primary)

Create a **T4 16GB** GPU pod (~$0.20–0.34/hr; your ~$1.50 ≈ 4–7 hrs — **stop the pod
after the showcase**). In the pod terminal:

```bash
pip install "vllm>=0.6.3"
vllm serve Qwen/Qwen3-8B-AWQ \
  --quantization awq --dtype float16 \
  --max-model-len 8192 --gpu-memory-utilization 0.90 \
  --guided-decoding-backend xgrammar --port 8000
```

Expose port **8000** in the pod's config → RunPod gives a stable URL
`https://<podid>-8000.proxy.runpod.net` (no ngrok needed). Verify:

```bash
curl https://<podid>-8000.proxy.runpod.net/v1/models   # → Qwen/Qwen3-8B-AWQ
```

**Fallback:** if credit runs out, run vLLM on Lightning + `ngrok http 8000` and use
that URL instead — only `LLM_BASE_URL` changes.

## 2. Backend + Postgres — DigitalOcean droplet

Droplet: Ubuntu 22.04, 4 GB. Install Docker + the compose plugin, then:

```bash
git clone <your-repo> && cd agentic_ecommerce_project
cp .env.example .env      # then edit .env — see keys below
```

Set in **`.env`**:
```
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://<podid>-8000.proxy.runpod.net/v1
OPENAI_MODEL=Qwen/Qwen3-8B-AWQ
OPENAI_API_KEY=vllm-no-key

DATABASE_URL=postgresql://smartshop:smartshop@db:5432/smartshop
DB_SSLMODE=disable
# Fallback DB (uncomment to switch back to Supabase, then restart):
# DATABASE_URL=postgresql://...supabase...:5432/postgres
# DB_SSLMODE=require

PINECONE_API_KEY=...        # keep Pinecone
PINECONE_INDEX_NAME=ecommerce
APP_USERNAME=admin
APP_PASSWORD_HASH=...       # generate with your usual hash step
JWT_SECRET=<random 48+ chars>
SUPABASE_URL=...            # storage for try-on/campaign images
SUPABASE_SERVICE_KEY=...
GOOGLE_API_KEY=...          # try-on / campaign image generation
```

Optional (for HTTPS): point a domain at the droplet IP and export it so Caddy gets a
Let's Encrypt cert:
```bash
export DOMAIN=api.yourshop.xyz
```

Launch (builds the api, starts Postgres seeded from `infra/seed.sql`, and Caddy):
```bash
docker compose -f infra/docker-compose.yml up -d --build
```
- Postgres loads `infra/seed.sql` on first boot → the exact 20 products with correct
  categories. The backend's `init_db()` then sees products present and skips its
  filename-based auto-seed. (To re-seed: `docker compose down -v` removes the volume.)
- Caddy serves HTTPS at `https://$DOMAIN` (or plain HTTP on :80 if `DOMAIN` unset).

## 3. Frontends — Vercel

Deploy `apps/customer` and `apps/owner` as two Vercel projects (free, auto-HTTPS).
For each, set the build env var:
```
NEXT_PUBLIC_API_URL=https://api.yourshop.xyz
```
(`apps/customer/src/lib/api.ts` reads it.)

## 4. Verify

```bash
curl https://api.yourshop.xyz/           # → 200
```
Then in the customer app: log in (`admin` / your password) and try:
- `show me shirts` → 3 shirts
- `do you have any red thisrt?` → only the red shirt
- `do you have drink?` → Sprite
- `wassup` → friendly chitchat, no products

Virtual try-on requires HTTPS (camera access). **After the showcase, stop the RunPod
pod** to preserve credit.

## Costs
- RunPod: ~$0.20–0.34/hr while running (~$1–1.5 for a showcase).
- Droplet: ~$24/mo for 4 GB (a $6/mo 1 GB droplet also works — backend is light).
- Vercel / Supabase / Pinecone: free tiers.
