#!/usr/bin/env bash
set -euo pipefail

# Scrape danych głosowań Rady Miasta Sopotu (BIP)
# Uruchom z katalogu radoskop-sopot/ lub z dowolnego miejsca

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Radoskop Sopot — scraper ==="
echo "Katalog projektu: $PROJECT_DIR"

# Setup venv
if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "[1/3] Tworzenie venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"

echo "[2/3] Instalacja zależności..."
pip install --quiet pymupdf requests playwright
playwright install chromium 2>/dev/null || true

echo "[3/3] Uruchamianie scrapera..."
python3 "$SCRIPT_DIR/scrape_sopot.py" \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  --cache-dir "$PROJECT_DIR/.cache" \
  "$@"

echo ""
echo "Gotowe: $PROJECT_DIR/docs/data.json"
echo "Aby przetestować najpierw: bash $0 --dry-run"
