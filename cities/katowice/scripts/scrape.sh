#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Radoskop Katowice — scraper ==="
echo "Katalog projektu: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "[1/4] Tworzenie venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"

echo "[2/4] Instalacja zaleznosci..."
pip install --quiet requests beautifulsoup4 pdfplumber playwright

echo "[3/4] Instalacja przegladarki (chromium)..."
python3 -m playwright install chromium --with-deps 2>/dev/null || python3 -m playwright install chromium

echo "[4/4] Uruchamianie scraperow..."

python3 "$SCRIPT_DIR/scrape_katowice.py" \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  --pdf-dir "$PROJECT_DIR/pdfs" \
  --parsed-dir "$PROJECT_DIR/cache/parsed" \
  "$@"

python3 "$SCRIPT_DIR/scrape_interpelacje.py" \
  --output "$PROJECT_DIR/docs/interpelacje.json" \
  "$@"

echo ""
echo "Gotowe!"
echo "  Glosowania: $PROJECT_DIR/docs/data.json"
echo "  Interpelacje: $PROJECT_DIR/docs/interpelacje.json"
