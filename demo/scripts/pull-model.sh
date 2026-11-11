#!/usr/bin/env bash
# Download the local LLM once into the Docker volume goys-ollama-models (requires internet).
# After this the demo runs the model fully offline. Model size on disk: about 1.3 GB (llama3.2:1b).
# Usage: scripts/pull-model.sh [model]      default model: llama3.2:1b (override with RCA_MODEL too)
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. /data); keep them as written.
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

MODEL="${1:-${RCA_MODEL:-llama3.2:1b}}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml)

# The volume is "external" in the compose file (so `down -v` never deletes the model): create it here.
docker volume create goys-ollama-models >/dev/null

echo "Starting the ollama service ..."
"${COMPOSE[@]}" up -d --no-deps ollama

echo "Pulling $MODEL (about 1.3 GB, only the first time) ..."
"${COMPOSE[@]}" exec -T ollama ollama pull "$MODEL"

echo
echo "Models in the volume:"
"${COMPOSE[@]}" exec -T ollama ollama list
echo
echo "Next: scripts/save-model.sh to make an offline backup of the volume."
