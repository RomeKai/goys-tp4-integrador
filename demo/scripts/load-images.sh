#!/usr/bin/env bash
# Load the offline image backup created by save-images.sh (no internet required).
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IN_FILE="${1:-$DEMO_DIR/images/goys-demo-images.tar}"

if [ ! -f "$IN_FILE" ]; then
  echo "File not found: $IN_FILE" >&2
  exit 1
fi

echo "Loading images from $IN_FILE ..."
docker load -i "$IN_FILE"
