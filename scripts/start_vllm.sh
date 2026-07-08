#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start_vllm.sh — Launch the local Qwen 2.5 vLLM server for SmartShop
#
# Usage:
#   ./scripts/start_vllm.sh                     # serve only
#   ./scripts/start_vllm.sh --tunnel             # serve + expose via ngrok
#
# IMPORTANT: vLLM runs in its OWN virtual environment (~/vllm-env),
# NOT in the project's .venv. This keeps the project clean for Render.
#
# First-time setup:
#   uv venv ~/vllm-env
#   uv pip install vllm --python ~/vllm-env
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-3B-Instruct-GPTQ-Int4}"
HOST="${VLLM_HOST:-127.0.0.1}"
PORT="${VLLM_PORT:-8002}"
GPU_UTIL="${VLLM_GPU_UTIL:-0.80}"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-4096}"
VLLM_ENV="${VLLM_ENV:-$HOME/vllm-env}"

echo "============================================================"
echo "  SmartShop — Local vLLM Server"
echo "============================================================"
echo "  Model:           $MODEL"
echo "  Host:            $HOST"
echo "  Port:            $PORT"
echo "  GPU Utilization:  $GPU_UTIL"
echo "  Max Model Len:   $MAX_MODEL_LEN"
echo "  vLLM venv:       $VLLM_ENV"
echo "============================================================"
echo ""

# Check the vLLM virtual environment exists
if [[ ! -f "$VLLM_ENV/bin/python" ]]; then
    echo "ERROR: vLLM virtual environment not found at $VLLM_ENV"
    echo ""
    echo "Create it instantly using uv:"
    echo "  uv venv $VLLM_ENV"
    echo "  uv pip install vllm --python $VLLM_ENV"
    exit 1
fi

# Start vLLM in the background
echo "[1/2] Starting vLLM server on port $PORT ..."
export PATH="$VLLM_ENV/bin:$PATH"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
"$VLLM_ENV/bin/python" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_UTIL" \
    --max-model-len "$MAX_MODEL_LEN" \
    --trust-remote-code \
    --enforce-eager \
    --enable-auto-tool-choice \
    --tool-call-parser hermes &

VLLM_PID=$!
echo "       vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready
echo "       Waiting for vLLM to load model ..."
READY=0
for i in $(seq 1 120); do
    if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
        echo "       vLLM is ready!"
        READY=1
        break
    fi
    sleep 2
done

if [[ "$READY" != "1" ]]; then
    echo "ERROR: vLLM did not become ready on http://$HOST:$PORT/health"
    kill $VLLM_PID 2>/dev/null || true
    exit 1
fi

# Optionally start ngrok tunnel
if [[ "${1:-}" == "--tunnel" ]]; then
    echo ""
    echo "[2/2] Starting ngrok tunnel ..."
    
    if ! command -v ngrok &> /dev/null; then
        echo "ERROR: ngrok not found. Install it: https://ngrok.com/download"
        echo "  Or:  pip install ngrok"
        kill $VLLM_PID 2>/dev/null
        exit 1
    fi
    
    ngrok http "$PORT" &
    NGROK_PID=$!
    
    sleep 3
    
    # Fetch the public URL from ngrok's local API
    TUNNEL_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
tunnels = data.get('tunnels', [])
for t in tunnels:
    if t.get('proto') == 'https':
        print(t['public_url'])
        break
" 2>/dev/null || echo "")
    
    if [[ -n "$TUNNEL_URL" ]]; then
        echo ""
        echo "============================================================"
        echo "  TUNNEL ACTIVE"
        echo "============================================================"
        echo ""
        echo "  Your vLLM is accessible at:"
        echo "    $TUNNEL_URL"
        echo ""
        echo "  Set this in Render's environment variables:"
        echo "    LLM_BASE_URL = ${TUNNEL_URL}/v1"
        echo ""
        echo "  Or in your local .env:"
        echo "    LLM_BASE_URL=${TUNNEL_URL}/v1"
        echo ""
        echo "============================================================"
    else
        echo "  WARNING: Could not detect ngrok tunnel URL."
        echo "  Check http://localhost:4040 manually."
    fi
    
    echo ""
    echo "Press Ctrl+C to stop both vLLM and ngrok."
    
    # Trap Ctrl+C to kill both processes
    trap "echo 'Shutting down...'; kill $VLLM_PID $NGROK_PID 2>/dev/null; exit 0" INT TERM
    wait $VLLM_PID
else
    echo ""
    echo "  vLLM is running at: http://localhost:$PORT"
    echo "  OpenAI-compatible endpoint: http://localhost:$PORT/v1"
    echo ""
    echo "  To expose to Render, run with --tunnel flag:"
    echo "    ./scripts/start_vllm.sh --tunnel"
    echo ""
    echo "Press Ctrl+C to stop."
    
    trap "echo 'Shutting down...'; kill $VLLM_PID 2>/dev/null; exit 0" INT TERM
    wait $VLLM_PID
fi
