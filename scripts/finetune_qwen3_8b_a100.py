#!/usr/bin/env python3
"""Fine-tune SmartShop's Qwen3-8B tool planner with QLoRA + Unsloth.

Uses the canonical Unsloth pattern:
  1. Load 4-bit base model with FastLanguageModel
  2. Apply LoRA adapters
  3. Format dataset as text via apply_chat_template (full convo, no thinking)
  4. Train with SFTTrainer + dataset_text_field="text"
  5. Apply train_on_responses_only() AFTER trainer creation to mask prompt tokens
     so loss is computed only on assistant completions (JSON plans).

Run on a Lightning AI GPU studio:
    python scripts/finetune_qwen3_8b_a100.py \\
      --dataset /teamspace/studios/this_studio/data/finetune_train.jsonl \\
      --output-dir /teamspace/studios/this_studio/models/qwen3-8b-smartshop-lora-v6 \\
      --epochs 2 --batch-size 8 --grad-accum 2 --max-seq-length 1024
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any


def import_training_stack() -> dict[str, Any]:
    # Unsloth must be imported before transformers so it can patch kernels.
    from unsloth import FastLanguageModel, train_on_responses_only

    import torch
    from datasets import load_dataset
    from trl import SFTTrainer

    try:
        from trl import SFTConfig
    except ImportError:
        SFTConfig = None

    return {
        "FastLanguageModel": FastLanguageModel,
        "train_on_responses_only": train_on_responses_only,
        "torch": torch,
        "load_dataset": load_dataset,
        "SFTTrainer": SFTTrainer,
        "SFTConfig": SFTConfig,
    }


def apply_qwen_chat_template(tokenizer: Any, messages: list[dict]) -> str:
    """Format one training sample with Qwen3 non-thinking chat template."""
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,   # disable <think> during training
        )
    except TypeError:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )


def validate_dataset(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        first = json.loads(handle.readline())
    if "messages" not in first:
        raise ValueError("Expected JSONL rows with a 'messages' field.")
    roles = [msg.get("role") for msg in first["messages"]]
    if roles != ["system", "user", "assistant"]:
        raise ValueError(f"Expected roles [system,user,assistant], got {roles}")


def run(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset)
    validate_dataset(dataset_path)
    stack = import_training_stack()

    FastLanguageModel = stack["FastLanguageModel"]
    train_on_responses_only = stack["train_on_responses_only"]
    load_dataset = stack["load_dataset"]
    torch = stack["torch"]
    SFTTrainer = stack["SFTTrainer"]
    SFTConfig = stack["SFTConfig"]

    print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
    print("Training base model:", args.model_id)
    print("Dataset:", dataset_path)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_id,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
        token=os.getenv("HF_TOKEN") or None,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )

    # ── Dataset: format as text strings ────────────────────────────────────
    raw = load_dataset("json", data_files=str(dataset_path), split="train")

    def format_row(example: dict) -> dict:
        return {"text": apply_qwen_chat_template(tokenizer, example["messages"])}

    formatted = raw.map(format_row, remove_columns=raw.column_names)
    split = formatted.train_test_split(test_size=args.eval_ratio, seed=3407)
    print("Train rows:", len(split["train"]), "Eval rows:", len(split["test"]))
    print("Example text preview (first 400 chars):\n", split["train"][0]["text"][:400])

    # ── SFT Trainer ────────────────────────────────────────────────────────
    bf16 = bool(torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 8)

    common_training_kwargs = dict(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        logging_steps=1,
        save_strategy="steps",
        save_steps=25,
        save_total_limit=2,
        report_to="none",
        optim="adamw_8bit",
        seed=3407,
        data_seed=3407,
        bf16=bf16,
        fp16=not bf16,
        gradient_checkpointing=True,
        dataset_text_field="text",
    )

    # Prefer SFTConfig (TRL ≥ 0.10) if available
    if SFTConfig is not None:
        try:
            import inspect
            sft_sig = inspect.signature(SFTConfig)
            cfg_kwargs = dict(common_training_kwargs)
            if "max_length" in sft_sig.parameters:
                cfg_kwargs["max_length"] = args.max_seq_length
            elif "max_seq_length" in sft_sig.parameters:
                cfg_kwargs["max_seq_length"] = args.max_seq_length
            if "packing" in sft_sig.parameters:
                cfg_kwargs["packing"] = False
            sft_config = SFTConfig(**cfg_kwargs)
            trainer = SFTTrainer(
                model=model,
                processing_class=tokenizer,
                args=sft_config,
                train_dataset=split["train"],
                eval_dataset=split["test"],
            )
        except TypeError as exc:
            print(f"SFTConfig path failed ({exc}), using legacy SFTTrainer API")
            SFTConfig = None

    if SFTConfig is None:
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=split["train"],
            eval_dataset=split["test"],
            dataset_text_field="text",
            max_seq_length=args.max_seq_length,
            packing=False,
            args=__import__("transformers").TrainingArguments(**{
                k: v for k, v in common_training_kwargs.items()
                if k != "dataset_text_field"
            }),
        )

    # ── Apply response-only masking (canonical Unsloth pattern) ────────────
    # These tokens are the ChatML instruction/response boundaries in Qwen3.
    # train_on_responses_only masks all tokens BEFORE <|im_start|>assistant
    # so the loss is only computed on the JSON plan completions.
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    # Verify labels are not all -100 on first sample
    sample = next(iter(trainer.get_train_dataloader()))
    labels = sample["labels"]
    non_masked = (labels != -100).sum().item()
    total = labels.numel()
    print(f"\nLabel sanity: {non_masked}/{total} tokens are training targets ({non_masked/total*100:.1f}%)")
    if non_masked == 0:
        raise RuntimeError(
            "All labels are -100! train_on_responses_only masking failed. "
            "Check that instruction_part/response_part match the tokenizer's chat template."
        )

    trainer.train()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    archive_path = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
    print("\nSaved LoRA adapter:", output_dir)
    print("Downloadable zip:", archive_path)
    print("\nServe later with:")
    print(
        f"vllm serve Qwen/Qwen3-8B --dtype bfloat16 --max-model-len 4096 "
        f"--enable-lora --max-lora-rank {args.lora_r} "
        f"--lora-modules smartshop={output_dir}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="unsloth/Qwen3-8B")
    parser.add_argument("--dataset", default="data/finetune_dataset.jsonl")
    parser.add_argument("--output-dir", default="models/qwen3-8b-smartshop-lora")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--eval-ratio", type=float, default=0.10)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
