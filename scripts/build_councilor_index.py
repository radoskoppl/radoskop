#!/usr/bin/env python3
"""
build_councilor_index.py

Buduje indeks radnych ze wszystkich miast Radoskopu.
Wynikowy plik councilors-index.json jest używany na stronie głównej radoskop.pl
do wyszukiwania radnych po nazwisku (szukajka globalna).

Czyta: ../radoskop-{miasto}/docs/data.json i profiles.json
Pisze: ../radoskop/docs/councilors-index.json
"""

import json
import os
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent  # gdansk-network/

CITY_DIRS = {
    "radoskop-bialystok": {"name": "Białystok", "url": "https://bialystok.radoskop.pl"},
    "radoskop-bydgoszcz": {"name": "Bydgoszcz", "url": "https://bydgoszcz.radoskop.pl"},
    "radoskop-gdansk": {"name": "Gdańsk", "url": "https://gdansk.radoskop.pl"},
    "radoskop-gdynia": {"name": "Gdynia", "url": "https://gdynia.radoskop.pl"},
    "radoskop-katowice": {"name": "Katowice", "url": "https://katowice.radoskop.pl"},
    "radoskop-krakow": {"name": "Kraków", "url": "https://krakow.radoskop.pl"},
    "radoskop-lodz": {"name": "Łódź", "url": "https://lodz.radoskop.pl"},
    "radoskop-lublin": {"name": "Lublin", "url": "https://lublin.radoskop.pl"},
    "radoskop-poznan": {"name": "Poznań", "url": "https://poznan.radoskop.pl"},
    "radoskop-sopot": {"name": "Sopot", "url": "https://sopot.radoskop.pl"},
    "radoskop-szczecin": {"name": "Szczecin", "url": "https://szczecin.radoskop.pl"},
    "radoskop-warszawa": {"name": "Warszawa", "url": "https://warszawa.radoskop.pl"},
    "radoskop-wroclaw": {"name": "Wrocław", "url": "https://wroclaw.radoskop.pl"},
}


def slugify(name):
    """Zamienia imię i nazwisko na slug URL."""
    s = unicodedata.normalize("NFD", name.lower())
    s = re.sub(r"[\u0300-\u036f]", "", s)  # strip diacritics
    s = s.replace("ł", "l").replace("Ł", "L")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def get_slug(name, profiles_data):
    """Szuka sluga w profiles.json; fallback na generowanie."""
    if profiles_data:
        for p in profiles_data.get("profiles", []):
            if p.get("name") == name:
                return p.get("slug", slugify(name))
    return slugify(name)


def build_index():
    index = []

    for dir_name, city_info in sorted(CITY_DIRS.items()):
        # Czytaj dane radnych z pliku kadencja-2024-2029.json (pełne dane)
        kadencja_path = BASE / dir_name / "docs" / "kadencja-2024-2029.json"
        data_path = BASE / dir_name / "docs" / "data.json"
        profiles_path = BASE / dir_name / "docs" / "profiles.json"

        profiles_data = None
        if profiles_path.exists():
            with open(profiles_path, "r", encoding="utf-8") as f:
                profiles_data = json.load(f)

        councilors = []

        # Preferuj kadencja-2024-2029.json (zawiera pełne dane radnych)
        if kadencja_path.exists():
            with open(kadencja_path, "r", encoding="utf-8") as f:
                kadencja_data = json.load(f)
            councilors = kadencja_data.get("councilors", [])

        # Fallback na data.json
        if not councilors and data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in data.get("kadencje", []):
                if k.get("id") == "2024-2029":
                    councilors = k.get("councilors", [])
                    break
        print(f"  {city_info['name']}: {len(councilors)} radnych")

        for c in councilors:
            name = c.get("name", "")
            if not name:
                continue

            slug = get_slug(name, profiles_data)

            entry = {
                "n": name,                               # name
                "c": city_info["name"],                   # city
                "u": city_info["url"],                    # city URL
                "s": slug,                                # slug
                "k": c.get("club", ""),                   # klub
                "f": round(c.get("frekwencja", 0), 1),   # frekwencja
                "a": round(c.get("aktywnosc", 0), 1),    # aktywnosc
                "z": round(c.get("zgodnosc_z_klubem", 0), 1),  # zgodnosc
            }
            index.append(entry)

    # Sortuj alfabetycznie po nazwisku (drugie słowo), potem imieniu
    def sort_key(e):
        parts = e["n"].split()
        if len(parts) >= 2:
            return (parts[-1].lower(), parts[0].lower())
        return (e["n"].lower(), "")

    index.sort(key=sort_key)

    output_path = BASE / "radoskop" / "docs" / "councilors-index.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = output_path.stat().st_size / 1024
    print(f"\nZapisano {len(index)} radnych do {output_path}")
    print(f"Rozmiar pliku: {size_kb:.1f} KB")


if __name__ == "__main__":
    print("Budowanie indeksu radnych...")
    build_index()
