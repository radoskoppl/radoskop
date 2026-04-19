#!/usr/bin/env bash
set -euo pipefail

# Scrape danych głosowań Rady Miasta Gdyni (bip.um.gdynia.pl)
# Uruchom z katalogu radoskop-gdynia/ lub z dowolnego miejsca
#
# Wymaga: Python 3.10+, Playwright (Chromium), PyMuPDF
#
# Użycie:
#   bash scripts/scrape.sh               # pełny scrape
#   bash scripts/scrape.sh --dry-run     # tylko lista sesji
#   bash scripts/scrape.sh --pdf-only scripts/pdfs/protokol_2026-01-14.pdf  # test parsera PDF
#   bash scripts/scrape.sh --max-sessions 3  # ogranicz do 3 sesji

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Radoskop Gdynia — scraper (BIP) ==="
echo "Katalog projektu: $PROJECT_DIR"

# Setup venv
if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "[1/4] Tworzenie venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"

echo "[2/4] Instalacja zależności Python..."
pip install --quiet requests pymupdf playwright

echo "[3/4] Instalacja Chromium (Playwright)..."
playwright install chromium 2>/dev/null || python3 -m playwright install chromium

echo "[4/4] Uruchamianie scrapera..."
python3 "$SCRIPT_DIR/scrape_gdynia.py" \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  --pdf-dir "$SCRIPT_DIR/pdfs" \
  "$@"

echo ""
echo "Gotowe: $PROJECT_DIR/docs/data.json"
echo ""
echo "Przydatne flagi:"
echo "  --dry-run          tylko lista sesji (bez pobierania)"
echo "  --max-sessions N   ogranicz do N sesji"
echo "  --pdf-only PLIK    przetestuj parser na jednym PDF"
