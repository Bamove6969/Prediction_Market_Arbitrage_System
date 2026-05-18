#!/bin/bash
# Universal entrypoint - IBKR Gateway + Backend + Ngrok + Colab Executor in one container

set -e

echo "=== Universal Arbitrage Scanner Startup ==="
echo "=== $(date) ==="

# Stub out VNC/noVNC before ibga's manager sources _run_xv.sh
# We export these so they are visible when manager.sh sources the script
export -f _run_vnc 2>/dev/null || true
export -f _run_novnc 2>/dev/null || true
# Patch the ibga xv script in-place to make VNC/noVNC no-ops
if grep -q "x11vnc" /opt/ibga/_run_xv.sh 2>/dev/null; then
    awk '
        /^function _run_vnc \{/{found=1; print; print "  : # noVNC disabled"; next}
        /^function _run_novnc \{/{found=1; print; print "  : # noVNC disabled"; next}
        found && /^\}$/{found=0; print; next}
        found{next}
        {print}
    ' /opt/ibga/_run_xv.sh > /tmp/_run_xv_patched.sh && \
    cp /tmp/_run_xv_patched.sh /opt/ibga/_run_xv.sh
    echo "    noVNC/x11vnc disabled"
fi

# Start IB Gateway manager in background
echo "[1/4] Starting IB Gateway (ibga manager)..."
/opt/ibga/manager.sh &
IBGA_PID=$!

# Give Xvfb and socat time to initialize before we start the Python stack
echo "    Waiting 15s for IB Gateway Xvfb/socat to initialize..."
sleep 15

# Start Ollama LLM server
echo "[2/5] Starting Ollama..."
ollama serve > /app/logs/ollama.log 2>&1 &
OLLAMA_PID=$!
sleep 5
echo "    Ollama started (check /app/logs/ollama.log)"

# Start ngrok tunnel
echo "[3/5] Starting ngrok tunnel..."
mkdir -p /root/.config/ngrok
ngrok config add-authtoken "$NGROK_AUTHTOKEN" --config /root/.config/ngrok/ngrok.yml
ngrok http 8000 \
    --config /root/.config/ngrok/ngrok.yml \
    --url=copyrightable-pseudocartilaginous-sade.ngrok-free.dev \
    --log=stdout \
    --log-level=info \
    > /app/logs/ngrok.log 2>&1 &
NGROK_PID=$!

sleep 5
echo "    Ngrok tunnel started (check /app/logs/ngrok.log)"

# Start Colab Executor service
echo "[4/5] Starting Colab Executor service..."
python3 /app/colab_executor.py > /app/logs/colab_executor.log 2>&1 &
EXECUTOR_PID=$!

sleep 3

# Start backend as main (foreground) process
echo "[5/5] Starting Arbitrage Backend..."
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Cleanup on exit
trap "kill $IBGA_PID $OLLAMA_PID $NGROK_PID $EXECUTOR_PID 2>/dev/null || true" EXIT
