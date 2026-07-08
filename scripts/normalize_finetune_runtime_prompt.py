#!/usr/bin/env python3
"""Normalize planner fine-tuning JSONL to match planner_v2.create_plan().

The runtime planner receives:

    Context:
    ...

    User request: ...

It does not receive Channel/Surface/Renderer metadata. This script strips those
training-only lines while preserving optional Context and User request content.
"""

from __future__ import annotations

import json
from pathlib import Path


DATASET_FILES = [
    Path("data/finetune_dataset.jsonl"),
    Path("data/finetune_train.jsonl"),
    Path("data/finetune_validation.jsonl"),
    Path("data/finetune_test.jsonl"),
]
MANIFEST = Path("data/finetune_manifest.json")


def normalize_user_content(content: str) -> str:
    marker = "\nUser request:"
    if marker not in content:
        return content

    before, request = content.rsplit(marker, 1)
    context = ""
    if "\nContext:\n" in before:
        context = before.split("\nContext:\n", 1)[1].strip()
    elif before.startswith("Context:\n"):
        context = before[len("Context:\n") :].strip()

    request = request.strip()
    parts: list[str] = []
    if context:
        parts.append(f"Context:\n{context}")
    parts.append(f"User request: {request}")
    return "\n\n".join(parts)


def normalize_file(path: Path) -> int:
    rows = []
    changed = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            old = row["messages"][1]["content"]
            new = normalize_user_content(old)
            if new != old:
                changed += 1
                row["messages"][1]["content"] = new
            rows.append(row)

    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return changed


def update_manifest(changed_by_file: dict[str, int]) -> None:
    if not MANIFEST.exists():
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["runtime_prompt_format"] = "Matches api.engine.planner_v2.create_plan(): optional Context block plus User request line."
    manifest["channel_metadata_in_user_prompt"] = False
    manifest["normalized_by"] = str(Path(__file__))
    manifest["normalized_rows"] = changed_by_file
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    changed_by_file: dict[str, int] = {}
    for path in DATASET_FILES:
        if path.exists():
            changed_by_file[str(path)] = normalize_file(path)
    update_manifest(changed_by_file)
    print("Normalized planner dataset prompt format:")
    for path, changed in changed_by_file.items():
        print(f"- {path}: {changed} rows changed")


if __name__ == "__main__":
    main()
