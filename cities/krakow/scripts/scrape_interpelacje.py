#!/usr/bin/env python3
"""
Scraper interpelacji i zapytań radnych z BIP Kraków.

Źródło: https://www.bip.krakow.pl/?sub_dok_id=192154&sub=interpelacje&co=shwInterp.php

Strona renderuje HTML-ową tabelę z kolumnami:
  - Imię i nazwisko Radnego/Radnej
  - Rodzaj dokumentu (I=interpelacja, Z=zapytanie)
  - Interpelacja/zapytanie w sprawie
  - Data otrzymania przez Prezydenta
  - Treść interpelacji/zapytania (link PDF)
  - Odpowiedź na interpelację/zapytanie (link PDF)

Filtry URL:
  - rodzaj=wszystkie | interpelacje | zapytania
  - sub_dok_id=192154 (IX kadencja 2024-2029)
  - sub_dok_id=148412 (VIII kadencja 2018-2023)

Użycie:
  python3 scrape_interpelacje.py [--output docs/interpelacje.json]
                                 [--kadencja IX]
                                 [--debug]
"""

import argparse
import json
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    print("Wymagany moduł: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Wymagany moduł: pip install beautifulsoup4")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://www.bip.krakow.pl"

KADENCJE = {
    "IX":   {"sub_dok_id": 192154, "label": "IX kadencja (2024–2029)"},
    # VIII kadencja (sub_dok_id=148412) — usunięta z BIP, strona przekierowuje na główną
}

HEADERS = {
    "User-Agent": "Radoskop/1.0 (https://krakow.radoskop.pl; kontakt@radoskop.pl)",
    "Accept": "text/html",
}

DELAY = 1.0


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def fetch_interpelacje_page(session, sub_dok_id, rodzaj="wszystkie",
                            page_size=5000, offset=0, debug=False):
    """Pobiera stronę ze wszystkimi interpelacjami dla danej kadencji.

    BIP Kraków paginuje wyniki parametrami:
      - ileWierszy: ile rekordów na stronę (domyślnie 10 na BIP, tu 5000 żeby pobrać wszystko)
      - ktory: offset (0-based)
    """
    url = BASE_URL
    params = {
        "sub_dok_id": sub_dok_id,
        "sub": "interpelacje",
        "co": "shwInterp.php",
        "rodzaj": rodzaj,
        "ileWierszy": page_size,
        "ktory": offset,
    }

    if debug:
        print(f"  [DEBUG] GET {url} params={params}")

    resp = session.get(url, headers=HEADERS, params=params, timeout=120)
    resp.raise_for_status()
    return resp.text


def parse_interpelacje_table(html, kadencja_name, debug=False):
    """Parsuje tabelę interpelacji z HTML.

    Kolumny tabeli:
      0: Imię i nazwisko Radnego/Radnej
      1: Rodzaj dokumentu* (I/Z)
      2: Interpelacja/zapytanie w sprawie
      3: Data otrzymania przez Prezydenta Miasta Krakowa
      4: Treść interpelacji/zapytania (link PDF)
      5: Odpowiedź na interpelację/zapytanie (link PDF)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find the main data table — it has the interpelacje data
    tables = soup.find_all("table")
    data_table = None
    for table in tables:
        # Look for table with "Imię i nazwisko" header
        header_text = table.get_text().lower()
        if "imię i nazwisko" in header_text and "rodzaj dokumentu" in header_text:
            data_table = table
            break

    if not data_table:
        print("  UWAGA: Nie znaleziono tabeli z interpelacjami!")
        if debug:
            print(f"  [DEBUG] Found {len(tables)} tables total")
        return []

    rows = data_table.find_all("tr")
    if debug:
        print(f"  [DEBUG] Found {len(rows)} rows in data table")

    records = []
    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        radny = cells[0].get_text(strip=True)
        rodzaj = cells[1].get_text(strip=True).upper()
        przedmiot = cells[2].get_text(strip=True)
        data_str = cells[3].get_text(strip=True)

        # PDF links
        tresc_url = ""
        odpowiedz_url = ""

        tresc_link = cells[4].find("a") if len(cells) > 4 else None
        if tresc_link:
            href = tresc_link.get("href", "")
            tresc_url = BASE_URL + href if href.startswith("/") else href

        odpowiedz_link = cells[5].find("a") if len(cells) > 5 else None
        if odpowiedz_link:
            href = odpowiedz_link.get("href", "")
            odpowiedz_url = BASE_URL + href if href.startswith("/") else href

        # Parse type
        typ = "interpelacja" if rodzaj == "I" else "zapytanie" if rodzaj == "Z" else "interpelacja"

        # Parse date
        data_wplywu = parse_date(data_str)

        # Extract year
        rok = int(data_wplywu[:4]) if data_wplywu and len(data_wplywu) >= 4 else 0

        record = {
            "typ": typ,
            "kadencja": kadencja_name,
            "rok": rok,
            "radny": radny,
            "przedmiot": przedmiot,
            "data_wplywu": data_wplywu,
            "tresc_url": tresc_url,
            "odpowiedz_url": odpowiedz_url,
            "data_odpowiedzi": "" if not odpowiedz_url else data_wplywu,  # BIP doesn't have separate answer date
            "odpowiedz_status": "udzielono odpowiedzi" if odpowiedz_url else "oczekuje na odpowiedź",
            "bip_url": f"{BASE_URL}/?sub_dok_id={KADENCJE[kadencja_name]['sub_dok_id']}&sub=interpelacje&co=shwInterp.php&rodzaj=wszystkie",
            "kategoria": classify_category(przedmiot),
        }

        records.append(record)

    return records


def parse_date(raw):
    """Konwertuje datę na format YYYY-MM-DD."""
    if not raw:
        return ""
    raw = raw.strip()
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw[:10]
    # DD.MM.YYYY
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # DD-MM-YYYY
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return raw


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

CATEGORIES = {
    "transport": ["transport", "komunikacj", "autobus", "tramwaj", "drog", "ulic", "rondo",
                  "chodnik", "przejści", "parkow", "rower", "ścieżk", "mpk", "przystank",
                  "sygnaliz", "skrzyżow"],
    "infrastruktura": ["infrastru", "remont", "naprawa", "budow", "inwesty", "moderniz",
                       "oświetl", "kanalizacj", "wodociąg", "nawierzch", "most", "murk"],
    "bezpieczeństwo": ["bezpiecz", "straż", "policj", "monitoring", "kradzież", "wandal",
                       "przestęp", "patrol", "alarm"],
    "edukacja": ["szkoł", "edukacj", "przedszkol", "żłob", "nauczyc", "kształc",
                 "oświat", "uczni"],
    "zdrowie": ["zdrow", "szpital", "leczni", "medyc", "lekarz", "przychodni",
                "ambulat"],
    "środowisko": ["środowisk", "zieleń", "drzew", "park ", "recykl", "odpady",
                   "śmieci", "klimat", "ekolog", "powietrz", "smog", "hałas"],
    "mieszkalnictwo": ["mieszka", "lokal", "zasob", "czynsz", "wspólnot", "kamieni",
                       "dewelop", "budynek", "osiedl"],
    "kultura": ["kultur", "bibliotek", "muzeum", "teatr", "koncert", "festiwal",
                "zabytek", "zabytk"],
    "sport": ["sport", "boisko", "stadion", "basen", "siłowni", "hala sport",
              "rekrea", "plac zabaw"],
    "pomoc społeczna": ["społeczn", "pomoc", "bezdomn", "senior", "niepełnospr",
                        "opiek", "zasiłk"],
    "budżet": ["budżet", "finansow", "wydatk", "dotacj", "środki", "pieniąd",
               "podatk", "umów", "rejestr"],
    "administracja": ["administrac", "urzęd", "pracowni", "regulam", "organizac",
                      "procedur", "biurokrac"],
}


def classify_category(przedmiot):
    """Klasyfikuje kategorię interpelacji na podstawie przedmiotu."""
    if not przedmiot:
        return "inne"
    text = przedmiot.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "inne"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape(kadencje, output_path, debug=False):
    """Główna funkcja scrapowania."""
    session = requests.Session()
    all_records = []

    for kad_name in kadencje:
        kad = KADENCJE.get(kad_name)
        if not kad:
            print(f"Nieznana kadencja: {kad_name}")
            continue

        sub_dok_id = kad["sub_dok_id"]
        print(f"\n=== {kad['label']} (sub_dok_id={sub_dok_id}) ===")

        try:
            html = fetch_interpelacje_page(session, sub_dok_id, debug=debug)
            records = parse_interpelacje_table(html, kad_name, debug=debug)
            print(f"  Sparsowano: {len(records)} rekordów")
            all_records.extend(records)
        except Exception as e:
            print(f"  BŁĄD: {e}")
            if debug:
                import traceback
                traceback.print_exc()

        time.sleep(DELAY)

    # Sort by date descending
    all_records.sort(key=lambda x: x.get("data_wplywu", ""), reverse=True)

    # Stats
    interp = sum(1 for r in all_records if r["typ"] == "interpelacja")
    zap = sum(1 for r in all_records if r["typ"] == "zapytanie")
    answered = sum(1 for r in all_records if r.get("odpowiedz_url"))
    print(f"\n=== Podsumowanie ===")
    print(f"Interpelacje: {interp}")
    print(f"Zapytania:    {zap}")
    print(f"Z odpowiedzią: {answered}")
    print(f"Razem:        {len(all_records)}")

    # Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nZapisano: {output_path} ({size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper interpelacji i zapytań radnych z BIP Kraków"
    )
    parser.add_argument(
        "--output", default="docs/interpelacje.json",
        help="Ścieżka do pliku wyjściowego (domyślnie: docs/interpelacje.json)"
    )
    parser.add_argument(
        "--kadencja", default="IX",
        help="Kadencja: IX lub 'all' (domyślnie: IX)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Włącz szczegółowe logowanie"
    )
    args = parser.parse_args()

    if args.kadencja.lower() == "all":
        kadencje = list(KADENCJE.keys())
    else:
        kadencje = [k.strip() for k in args.kadencja.split(",")]

    scrape(
        kadencje=kadencje,
        output_path=args.output,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
