#!/usr/bin/env bash
set -euo pipefail

# Pełny pipeline: scrape → generate site
# Uruchom z katalogu radoskop-warszawa/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 1/2 Scraping danych ==="
bash "$SCRIPT_DIR/scrape.sh"

echo "=== 2/2 Generowanie strony ==="
bash "$SCRIPT_DIR/generate.sh"

echo "=== Gotowe ==="
