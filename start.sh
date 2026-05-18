#!/bin/bash
echo "==================================================="
echo "    ARBITRAGE CALCULATOR INITIALIZATION SEQUENCE"
echo "==================================================="
echo ""

echo "[1/5] Terminating any ghost background processes..."
pkill -f "backend.main" 2>/dev/null
pkill -f "run_engine.py" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null
fuser -k 5000/tcp 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
pkill -f "ngrok" 2>/dev/null
sleep 3

echo "[2/5] Ensuring python dependencies are up to date..."
# Assume venv_linux exists
if [ -d "venv_linux" ]; then
    ./venv_linux/bin/pip install requests httpx fastapi uvicorn aiohttp aiosqlite ib_async >/dev/null 2>&1
else
    python3 -m venv venv_linux
    ./venv_linux/bin/pip install requests httpx fastapi uvicorn aiohttp aiosqlite ib_async >/dev/null 2>&1
fi

echo "[3/5] Booting up React Dashboard and API..."
npm run dev > dashboard.log 2>&1 &
sleep 5

echo "[4/5] Booting up AI Semantic Matcher (Port 8000)..."
if [ -d "venv_linux" ]; then
    ./venv_linux/bin/python -u -m backend.main > matcher.log 2>&1 &
else
    python3 -u -m backend.main > matcher.log 2>&1 &
fi
sleep 4

echo "[5/5] Booting up Real-time Arb Engine..."
if [ -d "venv_linux" ]; then
    ./venv_linux/bin/python -u run_engine.py > engine.log 2>&1 &
else
    python3 -u run_engine.py > engine.log 2>&1 &
fi
sleep 2

echo "Booting up Ngrok Tunnel for Cloud GPU..."
npx ngrok http 8000 --domain copyrightable-pseudocartilaginous-sade.ngrok-free.dev > ngrok.log 2>&1 &
sleep 8

echo "Opening dashboard in browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:5000/sentinel" &
elif command -v open &> /dev/null; then
    open "http://localhost:5000/sentinel" &
fi

echo ""
echo "==================================================="
echo "    ALL SYSTEMS ONLINE! (Running in background)"
echo "==================================================="
echo "Dashboard:     http://localhost:5000"
echo "ML API:        http://localhost:8000"
echo "Arb Engine:    (Active continuous loop)"
echo "Cloud Tunnel:  https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev"
echo ""
echo "Logs are piping to dashboard.log, matcher.log, engine.log, and ngrok.log."
echo "I'm not opening 4 terminal windows like Windows does because this is Linux and we aren't savages."