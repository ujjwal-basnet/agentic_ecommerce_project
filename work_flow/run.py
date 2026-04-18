#!/usr/bin/env python3
import subprocess
import time
import os
import sys

os.chdir("/home/ujjwal/delete/instagram")

proc = subprocess.Popen(
    [
        "./venv/bin/python",
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
print(f"Server started with PID: {proc.pid}")
time.sleep(2)

if proc.poll() is None:
    print("Server is running")
    sys.exit(0)
else:
    stdout, stderr = proc.communicate()
    print(f"Server died: {stdout.decode()} {stderr.decode()}")
    sys.exit(1)
