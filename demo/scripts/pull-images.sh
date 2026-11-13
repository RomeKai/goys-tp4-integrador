#!/usr/bin/env bash
# Prepare every image used by the demo, Acts 1, 2 and 3 (requires internet; run once while online).
#  - Public images (pinned versions) are pulled.
#  - Local images (goys-demo/tools, detector, rca, sender) are BUILT here, so that pip/apk run now
#    and not at the fair. save-images.sh then puts them in the offline tar.
# The image list is read from the compose files, so there is a single source of truth.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml)

echo "Building local images (tools, detector, rca, sender) ..."
"${COMPOSE[@]}" build

echo
echo "Pulling public images ..."
"${COMPOSE[@]}" pull --ignore-buildable

echo
echo "Images ready for offline use:"
"${COMPOSE[@]}" config --images | sort -u

echo
echo "The LLM model is separate (a Docker volume, not an image): run scripts/pull-model.sh next."
