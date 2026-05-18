#!/bin/bash
# Single container entrypoint - starts backend, ngrok, and colab executor

set -e

echo "=== Arbitrage Scanner - Single Container Startup ==="

# Create virtual display for Chromium
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Start ngrok in background
echo "Starting ngrok tunnel..."
mkdir -p /root/.config/ngrok
export NGROK_CONFIG=/root/.config/ngrok/ngrok.yml
ngrok config add-authtoken $NGROK_AUTHTOKEN --config $NGROK_CONFIG
ngrok http 8000 \
    --config $NGROK_CONFIG \
    --domain=copyrightable-pseudocartilaginous-sade.ngrok-free.dev \
    --log=stdout \
    --log-level=info &
NGROK_PID=$!

# Wait for ngrok to be ready
sleep 5

# Start Colab Executor in background
echo "Starting Colab Executor service..."
cd /app
python3 colab_executor.py > /app/logs/colab_executor.log 2>&1 &
EXECUTOR_PID=$!

# Wait for executor to be ready
sleep 3

# Start the backend (main process)
echo "Starting backend API..."
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Cleanup on exit
trap "kill $NGROK_PID $EXECUTOR_PID 2>/dev/null || true" EXIT
