#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Interpelacje Lublin — scraper ==="

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  python3 -m venv "$PROJECT_DIR/.venv"
fi
source "$PROJECT_DIR/.venv/bin/activate"

pip install --quiet requests beautifulsoup4

python3 "$SCRIPT_DIR/scrape_interpelacje.py" \
  --output "$PROJECT_DIR/docs/interpelacje.json" \
  "$@"

echo "Gotowe: $PROJECT_DIR/docs/interpelacje.json"
