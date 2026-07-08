#!/usr/bin/env python3
import subprocess
import time
import sys

SSH_HOST = "s_01kwtnwqrvybdqmrf1thgg78aq@ssh.lightning.ai"
REMOTE_MODEL_DIR = "/teamspace/studios/this_studio/models/qwen3-8b-smartshop-lora-v8"
REMOTE_ZIP_PATH = "/teamspace/studios/this_studio/models/qwen3-8b-smartshop-lora-v8.zip"
LOCAL_ZIP_PATH = "/home/ujjwal/codeagent/new/agentic_ecommerce_project/models/qwen3-8b-smartshop-lora-v8.zip"

def run_cmd(cmd, shell=True):
    res = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

print("SmartShop Automator: Starting check loop...", flush=True)

# 1. Wait for SFT process to finish
while True:
    code, stdout, stderr = run_cmd(f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "ps aux | grep finetune_qwen3_8b_a100.py | grep -v grep"')
    if code != 0 or not stdout:
        print("SmartShop Automator: Training process completed or stopped.", flush=True)
        break
    print("SmartShop Automator: Training is still active. Waiting 30s...", flush=True)
    time.sleep(30)

# 2. Check if the remote model dir was saved successfully
code, stdout, stderr = run_cmd(f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "ls -d {REMOTE_MODEL_DIR}"')
if code != 0:
    print(f"SmartShop Automator ERROR: Model directory {REMOTE_MODEL_DIR} does not exist on remote host!", flush=True)
    sys.exit(1)

# 3. Zip the model directory on the remote host
print("SmartShop Automator: Zipping model directory on remote host...", flush=True)
run_cmd(f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "cd /teamspace/studios/this_studio/models && zip -r qwen3-8b-smartshop-lora-v8.zip qwen3-8b-smartshop-lora-v8"')

# 4. Download the zip file to local machine
print("SmartShop Automator: Downloading zip file to local machine...", flush=True)
run_cmd(f'scp -o StrictHostKeyChecking=no {SSH_HOST}:{REMOTE_ZIP_PATH} {LOCAL_ZIP_PATH}')
print(f"SmartShop Automator: Successfully downloaded backup to {LOCAL_ZIP_PATH}", flush=True)

# 5. Kill any running vLLM servers
print("SmartShop Automator: Stopping any active remote vLLM servers...", flush=True)
run_cmd(f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "pkill -f vllm || true"')
time.sleep(2)

# 6. Start the new vLLM server pointing to v8
print("SmartShop Automator: Starting new remote vLLM server pointing to v8 adapter...", flush=True)
vllm_cmd = (
    f'ssh -o StrictHostKeyChecking=no {SSH_HOST} '
    f'\'nohup env VLLM_USE_V1=0 PATH=/system/conda/miniconda3/envs/cloudspace/bin:$PATH '
    f'/system/conda/miniconda3/envs/cloudspace/bin/python -m vllm.entrypoints.openai.api_server '
    f'--model Qwen/Qwen3-8B --dtype bfloat16 --max-model-len 4096 --gpu-memory-utilization 0.90 '
    f'--enable-lora --max-lora-rank 16 --lora-modules smartshop={REMOTE_MODEL_DIR} '
    f'--tokenizer {REMOTE_MODEL_DIR} --generation-config vllm --port 8000 > /tmp/vllm-smartshop-v8.log 2>&1 &\''
)
run_cmd(vllm_cmd)
print("SmartShop Automator: Serving started. Waiting 15s to check startup health...", flush=True)
time.sleep(15)

# 7. Check if vLLM server is responsive
code, stdout, stderr = run_cmd(f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "curl -s http://localhost:8000/v1/models"')
if "smartshop" in stdout:
    print("SmartShop Automator SUCCESS: New v8 model is successfully loaded and served on Lightning AI!", flush=True)
else:
    print(f"SmartShop Automator WARNING: vLLM did not register smartshop model. Response: {stdout}", flush=True)
