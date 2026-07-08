# Qwen3-8B SmartShop Fine-Tune on Lightning A100

Use this when you are in a hurry and have a Lightning AI A100 machine.

## What To Train

Train:

```text
unsloth/Qwen3-8B
```

Do not train:

```text
Qwen/Qwen3-8B-AWQ
```

AWQ is for inference. QLoRA training creates a LoRA adapter that is served on
top of a base or quantized base model later.

## Files

- Dataset: `data/finetune_dataset.jsonl`
- Training script: `scripts/finetune_qwen3_8b_a100.py`
- Notebook: `notebooks/finetune_qwen3_8b_a100.ipynb`
- Output adapter: `models/qwen3-8b-smartshop-lora/`
- Downloadable zip: `models/qwen3-8b-smartshop-lora.zip`

## A100 Notebook Steps

In Lightning AI, create an A100 notebook/studio, upload or clone this repo, then
open:

```text
notebooks/finetune_qwen3_8b_a100.ipynb
```

Run all cells. The main training command is:

```bash
python scripts/finetune_qwen3_8b_a100.py \
  --model-id unsloth/Qwen3-8B \
  --dataset data/finetune_dataset.jsonl \
  --output-dir models/qwen3-8b-smartshop-lora \
  --max-seq-length 2048 \
  --epochs 5 \
  --batch-size 4 \
  --grad-accum 2 \
  --learning-rate 2e-4 \
  --lora-r 16 \
  --lora-alpha 32
```

For the current 230-example dataset, expected time on an A100 is usually minutes,
not hours. If it overfits, rerun with `--epochs 3`.

## Download

After training, download:

```text
models/qwen3-8b-smartshop-lora.zip
```

Unzip it on the machine where you run vLLM:

```bash
unzip qwen3-8b-smartshop-lora.zip -d qwen3-8b-smartshop-lora
```

## Serve With vLLM

```bash
vllm serve Qwen/Qwen3-8B-AWQ \
  --quantization awq \
  --dtype float16 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.85 \
  --enable-lora \
  --max-lora-rank 16 \
  --lora-modules smartshop=/absolute/path/to/qwen3-8b-smartshop-lora \
  --port 8000
```

Then in `.env`:

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://YOUR-TUNNEL/v1
OPENAI_MODEL=smartshop
OPENAI_API_KEY=EMPTY
```

Check:

```bash
curl http://127.0.0.1:8000/v1/models
```

You should see both the base model and `smartshop`.
