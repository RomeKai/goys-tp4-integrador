#!/usr/bin/env bash
# Prepare every image used by the demo, Act 1 and Act 2 (requires internet; run once while online).
#  - Public images (pinned versions) are pulled.
#  - Local images (goys-demo/tools, goys-demo/detector) are BUILT here, so that pip/apk run now
#    and not at the fair. save-images.sh then puts them in the offline tar.
# The image list is read from the compose files, so there is a single source of truth.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.act2.yml)

echo "Building local images (tools, detector) ..."
"${COMPOSE[@]}" build detector netem

echo
echo "Pulling public images ..."
"${COMPOSE[@]}" pull --ignore-buildable

echo
echo "Images ready for offline use:"
"${COMPOSE[@]}" config --images | sort -u
