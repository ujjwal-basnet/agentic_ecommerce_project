#!/usr/bin/env bash
# Serve an OpenAI-compatible LLM with vLLM on a Lightning AI T4 Studio, and
# expose it with a public cloudflared URL your SmartShop app can point at.
#
# Run this INSIDE the Lightning Studio terminal (the T4 machine) — NOT on your
# 3 GB local box. A 7B AWQ needs ~16 GB VRAM (the T4 has exactly 16 GB).
#
# Usage:
#   bash scripts/serve_vllm_t4.sh
#
# Then copy the printed https://<...>.trycloudflare.com URL into your local
# .env as LLM_BASE_URL (with a trailing /v1) — see the bottom of this file.
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}"
QUANT="${QUANT:-awq}"          # T4 is Turing (SM75): use `awq`, NOT `awq_marlin`
PORT="${PORT:-8000}"
MAXLEN="${MAXLEN:-8192}"

echo ">> Installing vLLM + cloudflared (first run only)…"
pip install -q "vllm>=0.6.3"
if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL -o /tmp/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /tmp/cloudflared
  sudo mv /tmp/cloudflared /usr/local/bin/cloudflared 2>/dev/null || export PATH="/tmp:$PATH"
fi

echo ">> Starting vLLM: $MODEL ($QUANT, fp16) on :$PORT …"
vllm serve "$MODEL" \
  --quantization "$QUANT" \
  --dtype float16 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization 0.90 \
  --guided-decoding-backend xgrammar \
  --port "$PORT" &
VLLM_PID=$!

echo ">> Waiting for vLLM to load the model…"
until curl -fsS "http://localhost:${PORT}/v1/models" >/dev/null 2>&1; do
  sleep 3
  kill -0 "$VLLM_PID" 2>/dev/null || { echo "vLLM exited early — check the log above."; exit 1; }
done
echo ">> vLLM is up. Model id to use as OPENAI_MODEL:  $MODEL"

echo ">> Opening a public tunnel (copy the trycloudflare.com URL below)…"
cloudflared tunnel --url "http://localhost:${PORT}"
# ── When you have the URL (e.g. https://abc-def.trycloudflare.com), set locally:
#   LLM_PROVIDER=openai-compatible
#   LLM_BASE_URL=https://abc-def.trycloudflare.com/v1
#   OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
#   OPENAI_API_KEY=EMPTY
