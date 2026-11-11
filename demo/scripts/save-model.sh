#!/usr/bin/env bash
# Export the LLM volume (goys-ollama-models) into a tar so it can be restored without internet.
# Output: demo/images/goys-ollama-model.tar (git-ignored; ~1.3 GB for llama3.2:1b; copy it to a USB drive).
# Restore on another machine with: scripts/load-model.sh
# Run scripts/pull-model.sh first.
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. /data); keep them as written.
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

OUT_DIR="$DEMO_DIR/images"
OUT_FILE="$OUT_DIR/goys-ollama-model.tar"
OLLAMA_IMAGE="$(docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml config --images | grep '^ollama/ollama:')"
mkdir -p "$OUT_DIR"

if ! docker volume inspect goys-ollama-models >/dev/null 2>&1; then
  echo "Volume goys-ollama-models does not exist: run scripts/pull-model.sh first" >&2
  exit 1
fi

echo "Exporting the model volume to $OUT_FILE ..."
# The tar is streamed through stdout, so no host path has to be mounted (works the same on Windows).
docker run --rm --entrypoint tar -v goys-ollama-models:/data:ro "$OLLAMA_IMAGE" cf - -C /data . >"$OUT_FILE.part"
mv "$OUT_FILE.part" "$OUT_FILE"
ls -lh "$OUT_FILE"
echo "Done. Restore with scripts/load-model.sh"
