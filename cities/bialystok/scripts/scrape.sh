#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Radoskop Białystok — scraper ==="
echo "Katalog projektu: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "[1/3] Tworzenie venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"

echo "[2/3] Instalacja zależności..."
pip install --quiet requests beautifulsoup4 lxml

echo "[3/3] Uruchamianie scrapera..."
python3 "$SCRIPT_DIR/scrape_bialystok.py" \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  "$@"

echo ""
echo "Gotowe: $PROJECT_DIR/docs/data.json"
