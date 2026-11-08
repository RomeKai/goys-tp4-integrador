#!/usr/bin/env bash
# Pre-pull every image used by the demo (requires internet; run once while online).
# The image list is read from docker-compose.yml, so there is a single source of truth.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

echo "Pulling images defined in docker-compose.yml ..."
docker compose pull

echo
echo "Images ready for offline use:"
docker compose config --images | sort -u
