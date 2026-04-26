#!/usr/bin/env python3
"""
Radoskop Białystok — eSesja scraper (thin wrapper around scripts/lib_esesja.py).

Source: miastobialystok.esesja.pl
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

# Councillor names and club assignments for IX kadencja (2024-2029).
# Source: BIP Białystok, portal samorządowy.
COUNCILORS: dict[str, str] = {
    # KO — Koalicja Obywatelska (14)
    "Gracjan Eshetu-Gabre": "KO",
    "Katarzyna Kisielewska-Martyniuk": "KO",
    "Michał Karpowicz": "KO",
    "Marek Tyszkiewicz": "KO",
    "Jowita Chudzik": "KO",
    "Ewa Tokajuk": "KO",
    "Katarzyna Jamróz": "KO",
    "Anna Dobrowolska-Cylwik": "KO",
    "Karol Masztalerz": "KO",
    "Maciej Garley": "KO",
    "Anna Leonowicz": "KO",
    "Jarosław Grodzki": "KO",
    "Agnieszka Zabrocka": "KO",
    "Marcin Piętka": "KO",

    # PiS — Prawo i Sprawiedliwość (12)
    "Jacek Chańko": "PiS",
    "Krzysztof Stawnicki": "PiS",
    "Henryk Dębowski": "PiS",
    "Alicja Biały": "PiS",
    "Piotr Jankowski": "PiS",
    "Bartosz Stasiak": "PiS",
    "Katarzyna Ancipiuk": "PiS",
    "Katarzyna Siemieniuk": "PiS",
    "Sebastian Putra": "PiS",
    "Agnieszka Rzeszewska": "PiS",
    "Mateusz Sawicki": "PiS",
    "Paweł Myszkowski": "PiS",

    # Trzecia Droga (2)
    "Paweł Skowroński": "Trzecia Droga",
    "Joanna Misiuk": "Trzecia Droga",
}

if __name__ == "__main__":
    raise SystemExit(EsesjaScraper(
        base_url="https://miastobialystok.esesja.pl",
        kadencje=KADENCJE,
        councilors=COUNCILORS,
    ).run_cli(prog_name="Radoskop Białystok"))
