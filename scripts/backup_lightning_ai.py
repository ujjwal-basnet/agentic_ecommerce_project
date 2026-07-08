#!/usr/bin/env python3
"""
Lightning AI → Local Backup Script
Downloads all LoRA model adapters + training artifacts from Lightning AI.

Strategy:
- Downloads each version's essential files (adapter_model.safetensors, configs, tokenizer)
- Also downloads the pre-built zip files for the latest versions (v7, v8)
- Skips optimizer.pt in checkpoints (training-only, not needed for inference)
- Skips v3 zip (already fully downloaded locally)
- Shows real-time progress

Usage: python3 scripts/backup_lightning_ai.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SSH_HOST = "s_01kwtnwqrvybdqmrf1thgg78aq@ssh.lightning.ai"
SSH_KEY  = os.path.expanduser("~/.ssh/lightning_rsa")
SSH_OPTS = f"-i {SSH_KEY} -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=10"

REMOTE_BASE = "/teamspace/studios/this_studio"
LOCAL_BACKUP = Path(__file__).parent.parent / "lightning_ai_backup"

# Essential per-adapter files to download for each version (no optimizer.pt)
ADAPTER_ESSENTIAL_FILES = [
    "adapter_model.safetensors",
    "adapter_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "README.md",
]

# Model versions to backup
MODEL_VERSIONS = ["v3", "v4", "v5", "v6", "v7", "v8"]

# Zip files to download (skip v3 — already downloaded)
ZIPS_TO_DOWNLOAD = ["v4", "v5", "v6", "v7", "v8"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_scp(remote_path: str, local_path: str, recursive: bool = False) -> bool:
    """Run scp to download a file/dir. Returns True on success."""
    r_flag = "-r" if recursive else ""
    cmd = f'scp {SSH_OPTS} {r_flag} "{SSH_HOST}:{remote_path}" "{local_path}"'
    print(f"    ↓ {os.path.basename(remote_path)}", flush=True)
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"    ✗ ERROR: {result.stderr.strip()[:200]}", flush=True)
        return False
    return True


def human_size(path: Path) -> str:
    """Return human-readable size of a file."""
    try:
        size = path.stat().st_size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except Exception:
        return "?"


def section(title: str):
    print(f"\n{'═' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'═' * 60}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("", flush=True)
    section(f"Lightning AI → Local Backup  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Remote : {SSH_HOST}", flush=True)
    print(f"  Local  : {LOCAL_BACKUP}", flush=True)

    LOCAL_BACKUP.mkdir(parents=True, exist_ok=True)

    # ── 1. Download models: essential files per version ───────────────────────
    section("Models: Essential Adapter Files")
    models_dir = LOCAL_BACKUP / "models"
    models_dir.mkdir(exist_ok=True)

    for ver in MODEL_VERSIONS:
        model_name = f"qwen3-8b-smartshop-lora-{ver}"
        remote_model = f"{REMOTE_BASE}/models/{model_name}"
        local_model  = models_dir / model_name
        local_model.mkdir(exist_ok=True)

        print(f"\n  [{ver}] {model_name}", flush=True)

        ok_count = 0
        skip_count = 0
        for fname in ADAPTER_ESSENTIAL_FILES:
            local_f = local_model / fname
            # Skip if already present and non-empty
            if local_f.exists() and local_f.stat().st_size > 0:
                print(f"    ✓ {fname} ({human_size(local_f)}) — already exists, skipping", flush=True)
                skip_count += 1
                continue
            success = run_scp(f"{remote_model}/{fname}", str(local_f))
            if success:
                ok_count += 1

        print(f"  → {ok_count} downloaded, {skip_count} already present", flush=True)

    # ── 2. Download train-v8.log ───────────────────────────────────────────────
    section("Training Log")
    local_log = models_dir / "train-v8.log"
    if not local_log.exists():
        print("  Downloading train-v8.log...", flush=True)
        run_scp(f"{REMOTE_BASE}/models/train-v8.log", str(local_log))
    else:
        print(f"  ✓ train-v8.log already exists ({human_size(local_log)})", flush=True)

    # ── 3. Download model zips ─────────────────────────────────────────────────
    section("Model Zips (for complete backup)")
    print("  ⚠  Note: Check disk space before downloading zips (each ~620MB)", flush=True)

    # Get available disk space
    stat = os.statvfs(str(LOCAL_BACKUP))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    print(f"  💾 Available disk: {free_gb:.1f} GB", flush=True)

    for ver in ZIPS_TO_DOWNLOAD:
        model_name = f"qwen3-8b-smartshop-lora-{ver}"
        zip_name   = f"{model_name}.zip"
        remote_zip = f"{REMOTE_BASE}/models/{zip_name}"
        local_zip  = models_dir / zip_name

        if local_zip.exists() and local_zip.stat().st_size > 100_000_000:
            print(f"\n  [{ver}] ✓ {zip_name} ({human_size(local_zip)}) — already present", flush=True)
            continue

        # Re-check free space before each big download
        stat = os.statvfs(str(LOCAL_BACKUP))
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        if free_gb < 0.7:
            print(f"\n  [{ver}] ⚠ SKIPPED — only {free_gb:.2f} GB free (need ~0.7GB+)", flush=True)
            continue

        print(f"\n  [{ver}] Downloading {zip_name} (~620MB)...", flush=True)
        start = time.time()
        success = run_scp(remote_zip, str(local_zip))
        elapsed = time.time() - start
        if success:
            print(f"      Done in {elapsed:.0f}s → {human_size(local_zip)}", flush=True)

    # ── 4. Summary ────────────────────────────────────────────────────────────
    section("Backup Complete — Summary")
    total_size = 0
    file_count = 0
    for f in LOCAL_BACKUP.rglob("*"):
        if f.is_file():
            file_count += 1
            total_size += f.stat().st_size

    total_gb = total_size / (1024**3)
    print(f"  📁 Location  : {LOCAL_BACKUP}", flush=True)
    print(f"  📄 Files     : {file_count}", flush=True)
    print(f"  💾 Total size: {total_gb:.2f} GB", flush=True)
    print("", flush=True)

    # List what we got
    print("  Downloaded:", flush=True)
    for item in sorted(LOCAL_BACKUP.iterdir()):
        if item.is_dir():
            count = sum(1 for _ in item.rglob("*") if _.is_file())
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            print(f"    {item.name}/ — {count} files, {size/1024/1024:.1f} MB", flush=True)
        else:
            print(f"    {item.name} — {human_size(item)}", flush=True)


if __name__ == "__main__":
    main()
