#!/bin/bash
# Scrape uchwały Rady Miasta Gdańska from BAW
# Usage: ./scrape.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Scraping uchwały Gdańska ==="
python3 scrape_uchwaly.py

echo ""
echo "Done. Data saved to ../data/uchwaly.json"
