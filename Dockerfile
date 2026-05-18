# Dockerfile for Arbitrage Scanner with OpenRouter LLM
# ===========================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package installation
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install tocolab CLI for auto-uploading notebooks to Colab
RUN uv tool install tocolab

# Copy requirements first for better caching
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Install additional Python packages for Colab integration
RUN pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib websockets

# Copy the application
COPY backend/ backend/
COPY main.py .
COPY client/ client/
COPY start.sh .
COPY AGENTS.md .
COPY Cloud_GPU_Matcher_v3_Auto.ipynb .

# Expose ports (backend + dashboard)
EXPOSE 8000 5000

# Environment variables
ENV PYTHONPATH=/app
ENV IB_GATEWAY_URL=http://ibga:4000
ENV LLM_PROVIDER=openrouter

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Startup script
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
