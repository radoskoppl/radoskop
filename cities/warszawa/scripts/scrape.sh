#!/usr/bin/env bash
set -euo pipefail

# Scrape danych głosowań Rady m.st. Warszawy
# Uruchom z katalogu radoskop-warszawa/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

python3 -m venv "$PROJECT_DIR/.venv" 2>/dev/null || true
source "$PROJECT_DIR/.venv/bin/activate"
pip install --quiet playwright beautifulsoup4 lxml python-docx requests pymupdf
playwright install chromium 2>/dev/null

python3 "$SCRIPT_DIR/scrape_warszawa.py" \
  --kadencja all \
  --delay 1.0 \
  --output "$PROJECT_DIR/docs/data.json" \
  --profiles "$PROJECT_DIR/docs/profiles.json" \
  "$@"

echo "Gotowe: $PROJECT_DIR/docs/data.json"
