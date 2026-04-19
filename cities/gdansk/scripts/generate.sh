#!/usr/bin/env bash
set -euo pipefail

# Generuj index.html z szablonu + config.json
# Uruchom z katalogu radoskop-gdansk/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RADOSKOP_DIR="$(dirname "$PROJECT_DIR")/radoskop"

python3 "$RADOSKOP_DIR/scripts/generate_site.py" \
  --config "$PROJECT_DIR/config.json" \
  --output "$PROJECT_DIR/docs/"

echo "Gotowe: $PROJECT_DIR/docs/"
