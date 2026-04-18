#!/usr/bin/env python3
import subprocess
import time
import os
import sys
import signal

os.chdir("/home/ujjwal/delete/instagram")

os.environ["VERIFY_TOKEN"] = "ad - Test1"

server = subprocess.Popen(
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
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print(f"Server PID: {server.pid}")
time.sleep(2)

if server.poll() is not None:
    print("Server died!")
    sys.exit(1)

ngrok = subprocess.Popen(
    ["ngrok", "http", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print(f"NGrok PID: {ngrok.pid}")
time.sleep(5)

time.sleep(10000)
