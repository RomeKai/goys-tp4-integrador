#!/usr/bin/env bash
# Restore the LLM volume from the tar created by save-model.sh (no internet required).
# Usage: scripts/load-model.sh [file]       default: demo/images/goys-ollama-model.tar
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. /data); keep them as written.
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

IN_FILE="${1:-$DEMO_DIR/images/goys-ollama-model.tar}"
if [ ! -f "$IN_FILE" ]; then
  echo "File not found: $IN_FILE" >&2
  exit 1
fi
OLLAMA_IMAGE="$(docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml config --images | grep '^ollama/ollama:')"
if ! docker image inspect "$OLLAMA_IMAGE" >/dev/null 2>&1; then
  echo "Missing image $OLLAMA_IMAGE: run scripts/load-images.sh first" >&2
  exit 1
fi

docker volume create goys-ollama-models >/dev/null
echo "Restoring the model volume from $IN_FILE ..."
docker run --rm -i --entrypoint tar -v goys-ollama-models:/data "$OLLAMA_IMAGE" xf - -C /data <"$IN_FILE"
echo "Done. The model is in the volume goys-ollama-models:"
docker run --rm --entrypoint ls -v goys-ollama-models:/data:ro "$OLLAMA_IMAGE" /data/models/manifests/registry.ollama.ai/library
