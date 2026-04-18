#!/bin/bash
cd /home/ujjwal/delete/instagram

echo "Starting ngrok..."
ngrok http 8000 --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

sleep 4

echo "Starting FastAPI server..."
VERIFY_TOKEN=adadadas ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

sleep 2

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

echo ""
echo "========================================="
echo "  SERVER:      http://localhost:8000"
echo "  NGROK URL:   $NGROK_URL/webhook"
echo "  VERIFY TOKEN: adadadas"
echo "  STATUS:      $NGROK_URL/status"
echo "========================================="
echo ""
echo "Logs: tail -f server.log"
echo "Press Ctrl+C to stop"

wait
