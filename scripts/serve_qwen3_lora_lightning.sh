#!/usr/bin/env bash
# Serve SmartShop's Qwen3-8B AWQ model with the SmartShop LoRA adapter on
# Lightning AI, then optionally expose it with ngrok.
#
# Run this inside the Lightning Studio terminal.
#
# Usage:
#   bash scripts/serve_qwen3_lora_lightning.sh
#   bash scripts/serve_qwen3_lora_lightning.sh --tunnel
#
# If vLLM was installed into an existing Unsloth/training environment, NumPy ABI
# packages can break one at a time (scipy, sklearn, pandas). This script repairs
# the known binary package set before starting vLLM.

set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen3-8B-AWQ}"
LORA_NAME="${LORA_NAME:-smartshop}"
LORA_PATH="${LORA_PATH:-/teamspace/studios/this_studio/models/qwen3-8b-smartshop-lora-v2}"
PORT="${PORT:-8000}"
MAXLEN="${MAXLEN:-4096}"
GPU_UTIL="${GPU_UTIL:-0.85}"

echo "============================================================"
echo "  SmartShop Qwen3 LoRA vLLM Server"
echo "============================================================"
echo "  Model:      ${MODEL}"
echo "  LoRA:       ${LORA_NAME}=${LORA_PATH}"
echo "  Port:       ${PORT}"
echo "  Max len:    ${MAXLEN}"
echo "  GPU util:   ${GPU_UTIL}"
echo "============================================================"

if [[ ! -d "${LORA_PATH}" ]]; then
  echo "ERROR: LoRA adapter folder not found: ${LORA_PATH}"
  echo "Check the path or unzip the adapter first."
  exit 1
fi

echo ">> Repairing NumPy ABI packages used by vLLM import paths..."
python3 -m pip install -U --no-cache-dir "scipy>=1.15" "pandas>=2.3" "scikit-learn>=1.7"

echo ">> Checking Python/GPU package imports..."
python3 - <<'PY'
import torch, numpy, pandas, scipy, sklearn
print("torch:", torch.__version__)
print("numpy:", numpy.__version__)
print("pandas:", pandas.__version__)
print("scipy:", scipy.__version__)
print("sklearn:", sklearn.__version__)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY

echo ">> Starting vLLM..."
python3 -m vllm.entrypoints.openai.api_server \
  --model "${MODEL}" \
  --quantization awq \
  --dtype float16 \
  --max-model-len "${MAXLEN}" \
  --gpu-memory-utilization "${GPU_UTIL}" \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules "${LORA_NAME}=${LORA_PATH}" \
  --port "${PORT}" &

VLLM_PID=$!

echo ">> Waiting for vLLM to answer on /v1/models..."
for _ in $(seq 1 160); do
  if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
    echo ">> vLLM is ready."
    echo ""
    curl -s "http://127.0.0.1:${PORT}/v1/models"
    echo ""
    break
  fi
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "ERROR: vLLM exited early. Check the traceback above."
    exit 1
  fi
  sleep 3
done

if [[ "${1:-}" == "--tunnel" ]]; then
  if ! command -v ngrok >/dev/null 2>&1 && [[ ! -x ./ngrok ]]; then
    echo "ERROR: ngrok not found. Install ngrok or place ./ngrok in this directory."
    kill "${VLLM_PID}" 2>/dev/null || true
    exit 1
  fi

  echo ">> Starting ngrok tunnel..."
  if command -v ngrok >/dev/null 2>&1; then
    ngrok http "${PORT}"
  else
    ./ngrok http "${PORT}"
  fi
else
  echo ""
  echo "Server is local at: http://127.0.0.1:${PORT}/v1"
  echo "Use OPENAI_MODEL=${LORA_NAME}"
  echo ""
  echo "To expose it, open another terminal and run:"
  echo "  ngrok http ${PORT}"
  echo ""
  wait "${VLLM_PID}"
fi
