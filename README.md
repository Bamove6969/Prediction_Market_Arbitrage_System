# Prediction Market Arbitrage System

A real-time prediction market arbitrage scanner that finds mispriced markets across Polymarket, PredictIt, and Interactive Brokers to identify guaranteed profit opportunities.

## Features

- **Multi-Market Scanning**: Fetches markets from Polymarket (50k+ markets), PredictIt (900+), and IBKR Forecast (2k+)
- **Smart Matching**: Uses ML (sentence-transformers + cross-encoder) to find semantically similar markets across platforms
- **LLM Verification**: Uses Ollama (Gemma 4) to verify matches are truly the same event
- **Docker Ready**: Full containerization with IB Gateway integration
- **Web Dashboard**: Real-time monitoring interface

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Arbitrage Backend                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ Polymarket│  │PredictIt │  │ IBKR     │              │
│  │  Fetcher │  │ Fetcher  │  │ Fetcher  │              │
│  └────┬────┘  └────┬────┘  └────┬────┘              │
│       └────────────┼────────────┘                     │
│                    ▼                                   │
│         ┌─────────────────┐                           │
│         │  Market Scanner │                           │
│         │  + Matcher     │                           │
│         └───────┬───────┘                           │
│                 ▼                                   │
│         ┌─────────────────┐                         │
│         │  Ollama LLM      │                         │
│         │  Verification  │                         │
│         └───────┬───────┘                           │
│                 ▼                                   │
│         ┌─────────────────┐                         │
│         │  Dashboard API  │                         │
│         └─────────────────┘                         │
└─────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
    ┌─────────────────┐      ┌─────────────────┐
    │ Docker Compose  │      │   Colab GPU     │
    │ (IB Gateway)   │      │   Processing   │
    └─────────────────┘      └─────────────────┘
```

## Quick Start

### With Docker

```bash
# Clone and start
git clone https://github.com/bamove6969/Prediction_Market_Arbitrage_System.git
cd Prediction_Market_Arbitrage_System
docker-compose up -d

# Check status
curl http://localhost:8001/api/scan-status
```

### Manual Setup

```bash
# Create venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
PYTHONPATH=. python -m uvicorn backend.main:app --port 8000
```

## API Endpoints

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/api/scan` | POST | Trigger market scan |
| `/api/scan-status` | GET | Check scan progress |
| `/api/raw-markets` | GET | All markets (for Colab) |
| `/api/cloud-results` | POST | Receive Colab matches |
| `/api/arbitrage-opportunities` | GET | Found opportunities |

## External Services Required

- **IB Gateway**: Docker container connects automatically via `http://ibga:4000`
- **Ollama**: For local LLM verification (uses Gemma 4 or Qwen)
- **Colab**: For GPU-accelerated ML matching

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **ML**: sentence-transformers, cross-encoder
- **LLM**: Ollama (Gemma 4 / Qwen 3.6)
- **Data**: IB-insync, aiohttp, httpx
- **Docker**: Multi-container orchestration

## Disclaimer

This is for educational purposes. Always verify arbitrage opportunities manually before trading. Markets may have liquidity constraints, fees, and settlement risks not accounted for in ROI calculations.

## License

MIT License - Use at your own risk.