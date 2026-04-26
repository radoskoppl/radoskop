#!/usr/bin/env python3
"""
Radoskop Bytom — eSesja scraper (thin wrapper around scripts/lib_esesja.py).

Edit COUNCILORS to map councillor names to club codes when you have the data.
Without it, frekwencja/aktywnosc/votes still work, only club-loyalty stays empty.
"""

import sys
from pathlib import Path

# Make the shared library importable from monorepo: radoskop/scripts/lib_esesja.py
HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "scripts"))

from lib_esesja import EsesjaScraper

KADENCJE = {
    "2024-2029": {"label": "IX kadencja (2024–2029)", "start": "2024-05-07"},
}

# Optional: map "Lastname Firstname" (eSesja format) or "Firstname Lastname"
# to the club code. Leave empty until you have the council composition.
COUNCILORS: dict[str, str] = {}

if __name__ == "__main__":
    raise SystemExit(EsesjaScraper(
        base_url="https://bytom.esesja.pl",
        kadencje=KADENCJE,
        councilors=COUNCILORS,
    ).run_cli(prog_name="Radoskop Bytom (https://bytom.esesja.pl)"))
