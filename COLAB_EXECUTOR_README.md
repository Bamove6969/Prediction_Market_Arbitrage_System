# Colab Auto-Executor Service
Runs on Oracle Cloud to automatically execute Colab notebooks via headless browser.

## Setup on Oracle Cloud VM

### 1. Install dependencies
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv chromium-browser

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install flask selenium webdriver-manager
```

### 2. Configure environment
```bash
# Set your ngrok backend URL (where results get sent)
export BACKEND_URL="https://your-ngrok-url.ngrok.io"

# Optional: Telegram bot for notifications
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### 3. Run the service
```bash
# As a background service
nohup python3 colab_executor.py > colab_executor.log 2>&1 &

# Or use systemd for auto-start
sudo cp colab-executor.service /etc/systemd/system/
sudo systemctl enable colab-executor
sudo systemctl start colab-executor
```

### 4. Test
```bash
curl http://localhost:5000/status
curl -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"gist_id": "test123", "owner": "Bamove6969"}'
```

## How It Works

1. **Scanner uploads notebook to GitHub Gist** (after IBKR scans complete)
2. **Scanner calls Oracle executor** with gist_id
3. **Oracle Cloud spins up headless Chrome**
4. **Opens Colab notebook URL**
5. **Waits for runtime to connect** (GPU allocation ~30-60s)
6. **Auto-execute triggers** (first cell has auto-run code)
7. **Notebook processes markets** via ngrok tunnel
8. **Results sent back** to your backend via WebSocket

## Monitoring

- Check logs: `tail -f colab_executor.log`
- Check queue: `curl http://localhost:5000/status`
- Systemd status: `systemctl status colab-executor`

## Notes

- Oracle Cloud ARM instances work great (free tier: 4 OCPU, 24GB RAM)
- Colab free tier gives ~12 hours runtime
- Notebook has auto-execute code in first cell - no manual intervention needed
- Results flow back through ngrok tunnel to `/api/cloud-results` endpoint
