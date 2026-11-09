#!/usr/bin/env bash
# Save every demo image into a single tar for offline backup.
# Output: demo/images/goys-demo-images.tar (git-ignored; copy it to a USB drive).
# Restore on another machine with: demo/scripts/load-images.sh
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

OUT_DIR="$DEMO_DIR/images"
OUT_FILE="$OUT_DIR/goys-demo-images.tar"
mkdir -p "$OUT_DIR"

mapfile -t IMAGES < <(docker compose config --images | sort -u)

# Make sure every image is present locally before saving.
for img in "${IMAGES[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "Missing locally: $img -> run scripts/pull-images.sh first" >&2
    exit 1
  fi
done

echo "Saving ${#IMAGES[@]} images to $OUT_FILE ..."
docker save -o "$OUT_FILE" "${IMAGES[@]}"
ls -lh "$OUT_FILE"
echo "Done. Restore with scripts/load-images.sh"
