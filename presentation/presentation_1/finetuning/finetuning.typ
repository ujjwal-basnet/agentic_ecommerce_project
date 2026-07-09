#import "../../template.typ": title-slide, slide-layout, divider-slide

#title-slide(
  title: "Qwen3-8B SmartShop Fine-Tuning",
  subtitle: "Part 2: Instruction Tuning for Planner Accuracy",
  author: "researchcontentlab@gmail.com",
  project: "project-ba58c036-070e-438e-b8b"
)

#pagebreak()

#show: slide-layout.with(title: "Why Fine-Tune?", section: "Finetune Intro")

- General-purpose LLMs struggle to consistently output structured *JSON plans* matching exact API schemas.
- Hallucinations in tool names or missing dependency links break execution.
- Fine-tuning adapts a base model (*Qwen3-8B*) to:
  - Generate valid JSON plans under schema constraints.
  - Correctly invoke domain-specific e-commerce capabilities.
  - Parse subjective descriptions (e.g. colors, synonyms) into structured SQL lookups.

#pagebreak()

#show: slide-layout.with(title: "The Dataset Format", section: "Dataset Format")

- Main training file: `data/finetune_dataset.jsonl` (1167 augmented instances).
- Structure: Instruction-Response JSON pairs.

*Sample Dataset Item:*
```json
{
  "instruction": "I want to buy a blue Kurti readymade suit",
  "response": {
    "capabilities": ["search_products"],
    "parameters": {
      "category": "Suit",
      "color": "blue"
    }
  }
}
```

#pagebreak()

#show: slide-layout.with(title: "Training Script & Execution", section: "Training Script")

- Script: `scripts/finetune_qwen3_8b_a100.py`
- Utilizes *Unsloth* and *QLoRA* on a Lightning AI A100 GPU for fast training.

*Execution Command:*
```bash
python scripts/finetune_qwen3_8b_a100.py \
  --model-id unsloth/Qwen3-8B \
  --dataset data/finetune_dataset.jsonl \
  --output-dir models/qwen3-8b-smartshop-lora \
  --max-seq-length 2048 \
  --epochs 5 --batch-size 4 --grad-accum 2 \
  --learning-rate 2e-4 --lora-r 16 --lora-alpha 32
```

#pagebreak()

#show: slide-layout.with(title: "Serving Architecture", section: "Model Serving")

- The trained adapter is packaged as `models/qwen3-8b-smartshop-lora.zip`.
- Served on a GPU server using *vLLM* with active LoRA support:

```bash
vllm serve Qwen/Qwen3-8B-AWQ \
  --quantization awq --enable-lora \
  --max-lora-rank 16 \
  --lora-modules smartshop=/path/to/lora_dir \
  --port 8000
```

- An *ngrok* HTTPS tunnel bridges the local GPU endpoint to the public web API.
