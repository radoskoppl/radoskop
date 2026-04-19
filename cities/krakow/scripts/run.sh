#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Install deps
pip install -q requests beautifulsoup4 lxml pdfplumber

# Run scraper, pass through all args
python3 scripts/scrape_krakow.py --output docs/data.json --profiles docs/profiles.json "$@"
