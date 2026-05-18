#!/bin/bash
set -e

echo "🚀 Starting Arbitrage Container (OpenRouter LLM)..."

# Skip Ollama entirely - using OpenRouter for LLMs
echo "⏭️  Skipping Ollama setup (using OpenRouter)"

# Start the main application
echo "🚀 Starting FastAPI backend..."
exec "$@"
