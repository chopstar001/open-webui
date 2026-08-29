#!/bin/bash

image_name="open-webui"
container_name="open-webui"
host_port=3000
container_port=8080

# ── TASA WebUI environment variables ──────────────────────────
# OpenRouter (replaces Ollama for LLM inference)
OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://openrouter.ai/api/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"

# Ollama base URL (kept for compatibility; user primarily uses OpenRouter)
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://host.docker.internal:11434}"

# SHKeeper crypto payment gateway (billing integration)
SHKEEPER_API_URL="${SHKEEPER_API_URL:-http://host.docker.internal:5555}"
SHKEEPER_API_KEY="${SHKEEPER_API_KEY:-n29zHQmezdSQjiB-gNj8SQ}"
SHKEEPER_WEBHOOK_SECRET="${SHKEEPER_WEBHOOK_SECRET:-}"

docker build -t "$image_name" .
docker stop "$container_name" &>/dev/null || true
docker rm "$container_name" &>/dev/null || true

docker run -d -p "$host_port":"$container_port" \
    --add-host=host.docker.internal:host-gateway \
    -v "open-webui_open-webui:/app/backend/data" \
    --name "$container_name" \
    --restart always \
    -e "OLLAMA_BASE_URL=$OLLAMA_BASE_URL" \
    -e "OPENAI_API_BASE_URL=$OPENAI_API_BASE_URL" \
    -e "OPENAI_API_KEY=$OPENAI_API_KEY" \
    -e "SHKEEPER_API_URL=$SHKEEPER_API_URL" \
    -e "SHKEEPER_API_KEY=$SHKEEPER_API_KEY" \
    -e "SHKEEPER_WEBHOOK_SECRET=$SHKEEPER_WEBHOOK_SECRET" \
    "$image_name"

docker image prune -f
