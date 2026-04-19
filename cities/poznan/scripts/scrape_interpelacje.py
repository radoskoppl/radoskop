#!/usr/bin/env python3
"""
Scraper interpelacji i zapytań radnych z BIP Poznań.

Źródło: https://bip.poznan.pl/bip/interpelacje/

API JSON: https://bip.poznan.pl/api-json/bip/interpelacje/{page}/
  - Paginacja: 50 rekordów na stronę, strona 1-bazowa
  - Filtrowanie: ?co=search&kadencja_in=IX+Kadencja+Rady+Miasta
  - Struktura: bip.poznan.pl → data[0] → interpelacje → items[0] → interpelacja[]
  - Każda interpelacja: link, noteid, kadencja, data_wplywu, symbol, wnioskodawca, temat, zalaczniki

Załączniki (zalaczniki → items[] → zalacznik[]):
  - opis: zawsze "interpelacja"
  - nazwa: "interpel_85.pdf", "odpowiedz_na_interpelacje_nr_174.rtf", "zal_interpel_85.pdf"
  - Odpowiedź rozpoznajemy po "odpowied" w nazwie pliku
  - link, id, mime, length

Kadencje:
  - IX Kadencja Rady Miasta (2024–2029)
  - VIII Kadencja Rady Miasta (2018–2023)
  - VII Kadencja Rady Miasta (2014–2018)
  - VI Kadencja Rady Miasta (2010–2014)
  - V Kadencja Rady Miasta (2006–2010)

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


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "https://bip.poznan.pl/api-json/bip/interpelacje"
BIP_BASE = "https://bip.poznan.pl"

KADENCJE = {
    "IX":   {"filter": "IX Kadencja Rady Miasta",   "label": "IX kadencja (2024–2029)"},
    "VIII": {"filter": "VIII Kadencja Rady Miasta",  "label": "VIII kadencja (2018–2023)"},
    "VII":  {"filter": "VII Kadencja Rady Miasta",   "label": "VII kadencja (2014–2018)"},
    "VI":   {"filter": "VI Kadencja Rady Miasta",    "label": "VI kadencja (2010–2014)"},
    "V":    {"filter": "V Kadencja Rady Miasta",     "label": "V kadencja (2006–2010)"},
}

HEADERS = {
    "User-Agent": "Radoskop/1.0 (https://poznan.radoskop.pl; kontakt@radoskop.pl)",
    "Accept": "application/json",
}

DELAY = 0.5
PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_page(session, page, kadencja_filter=None, debug=False):
    """Pobiera stronę z interpelacjami z API JSON."""
    url = f"{API_BASE}/{page}/" if page > 1 else f"{API_BASE}/"
    params = {}
    if kadencja_filter:
        params["co"] = "search"
        params["kadencja_in"] = kadencja_filter

    if debug:
        print(f"  [DEBUG] GET {url} params={params}")

    resp = session.get(url, headers=HEADERS, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Navigate nested structure: bip.poznan.pl → data[0] → interpelacje
    root = data.get("bip.poznan.pl", {})
    interp_data = root.get("data", [{}])[0].get("interpelacje", {})

    total = interp_data.get("total_size", 0)
    items_wrapper = interp_data.get("items", [])

    records = []
    if items_wrapper:
        records = items_wrapper[0].get("interpelacja", [])
        # Handle case where it's a single object, not array
        if isinstance(records, dict):
            records = [records]

    return records, total


def extract_attachments(item):
    """Wyciąga URLe załączników (treść i odpowiedź) z interpelacji."""
    tresc_url = ""
    odpowiedz_url = ""

    zalaczniki = item.get("zalaczniki", {})
    if not zalaczniki or not isinstance(zalaczniki, dict):
        return tresc_url, odpowiedz_url

    items = zalaczniki.get("items", [])
    for wrapper in items:
        zal_data = wrapper.get("zalacznik", [])

        # Can be array or single object
        if isinstance(zal_data, dict):
            zal_data = [zal_data]

        for zal in zal_data:
            nazwa = (zal.get("nazwa", "") or "").lower()
            link = zal.get("link", "")

            if "odpowied" in nazwa:
                if not odpowiedz_url:
                    odpowiedz_url = link
            elif not tresc_url:
                tresc_url = link

    return tresc_url, odpowiedz_url


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def flip_name(name):
    """Odwraca 'Nazwisko Imię' → 'Imię Nazwisko'.

    BIP Poznań zwraca wnioskodawcę w formacie 'Nazwisko Imię'.
    Obsługuje też nazwiska wieloczłonowe po myślniku, np.
    'Kowalska-Nowak Anna' → 'Anna Kowalska-Nowak'.
    Obsługuje 'vel' w nazwisku, np.
    'Szynkowska vel Sęk Sara' → 'Sara Szynkowska vel Sęk'.
    """
    if not name:
        return name
    parts = name.strip().split()
    if len(parts) < 2:
        return name
    # Handle 'vel' in surname: everything up to and including 'vel X' is surname
    try:
        vel_idx = [p.lower() for p in parts].index("vel")
        # surname = parts[0:vel_idx+2], firstname = parts[vel_idx+2:]
        surname_parts = parts[: vel_idx + 2]
        first_parts = parts[vel_idx + 2 :]
        if first_parts:
            return " ".join(first_parts) + " " + " ".join(surname_parts)
        return name  # no first name found, return as-is
    except ValueError:
        pass
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    # Assume first token is surname (possibly hyphenated), rest is first name(s)
    return " ".join(parts[1:]) + " " + parts[0]


def classify_type(temat):
    """Klasyfikuje typ na podstawie tematu."""
    if not temat:
        return "interpelacja"
    t = temat.lower()
    if t.startswith("zapytanie"):
        return "zapytanie"
    return "interpelacja"


def kadencja_to_roman(kadencja_str):
    """Wyciąga numer kadencji z pełnej nazwy."""
    # "IX Kadencja Rady Miasta" → "IX"
    m = re.match(r"^([IVXLC]+)\s", kadencja_str)
    if m:
        return m.group(1)
    return kadencja_str


def parse_record(item):
    """Parsuje pojedynczy rekord interpelacji z API."""
    temat = (item.get("temat", "") or "").strip()
    data_wplywu = (item.get("data_wplywu", "") or "").strip()[:10]
    wnioskodawca_raw = (item.get("wnioskodawca", "") or "").strip()
    # BIP zwraca "Nazwisko Imię" — przy wielu autorach oddzielonych przecinkiem
    # np. "Szabelski Adam, Kapustka Łukasz, Plewiński Przemysław"
    if "," in wnioskodawca_raw:
        wnioskodawca = ", ".join(flip_name(n.strip()) for n in wnioskodawca_raw.split(",") if n.strip())
    else:
        wnioskodawca = flip_name(wnioskodawca_raw)
    symbol = (item.get("symbol", "") or "").strip()
    kadencja_raw = (item.get("kadencja", "") or "").strip()
    link = (item.get("link", "") or "").strip()

    # Extract year
    rok = int(data_wplywu[:4]) if data_wplywu and len(data_wplywu) >= 4 else 0

    # Kadencja
    kadencja = kadencja_to_roman(kadencja_raw)

    # Type
    typ = classify_type(temat)

    # Attachments
    tresc_url, odpowiedz_url = extract_attachments(item)

    # Answer status
    odpowiedz_status = "udzielono odpowiedzi" if odpowiedz_url else "oczekuje na odpowiedź"

    return {
        "typ": typ,
        "kadencja": kadencja,
        "rok": rok,
        "radny": wnioskodawca,
        "przedmiot": temat,
        "data_wplywu": data_wplywu,
        "data_odpowiedzi": "",
        "tresc_url": tresc_url,
        "odpowiedz_url": odpowiedz_url,
        "odpowiedz_status": odpowiedz_status,
        "bip_url": link,
        "symbol": symbol,
        "kategoria": classify_category(temat),
    }


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

CATEGORIES = {
    "transport": ["transport", "komunikacj", "autobus", "tramwaj", "drog", "ulic", "rondo",
                  "chodnik", "przejści", "parkow", "rower", "ścieżk", "mpk", "przystank",
                  "sygnaliz", "skrzyżow", "ztm"],
    "infrastruktura": ["infrastru", "remont", "naprawa", "budow", "inwesty", "moderniz",
                       "oświetl", "kanalizacj", "wodociąg", "nawierzch", "most"],
    "bezpieczeństwo": ["bezpiecz", "straż", "policj", "monitoring", "kradzież", "wandal",
                       "przestęp", "patrol"],
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
               "podatk"],
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

        kadencja_filter = kad["filter"]
        print(f"\n=== {kad['label']} ===")

        page = 1
        total = None
        kad_records = []

        while True:
            try:
                records, total_size = fetch_page(
                    session, page,
                    kadencja_filter=kadencja_filter,
                    debug=debug
                )
            except Exception as e:
                print(f"  BŁĄD na stronie {page}: {e}")
                if debug:
                    import traceback
                    traceback.print_exc()
                break

            if total is None:
                total = total_size
                total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
                print(f"  Łącznie: {total} interpelacji ({total_pages} stron)")

            for item in records:
                record = parse_record(item)
                kad_records.append(record)

            if debug:
                print(f"  Strona {page}/{total_pages}: {len(records)} rekordów")
            elif page % 10 == 0:
                print(f"  Strona {page}/{total_pages}...")

            if not records or page >= total_pages:
                break

            page += 1
            time.sleep(DELAY)

        print(f"  Pobrano: {len(kad_records)} rekordów")
        all_records.extend(kad_records)

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
        description="Scraper interpelacji i zapytań radnych z BIP Poznań"
    )
    parser.add_argument(
        "--output", default="docs/interpelacje.json",
        help="Ścieżka do pliku wyjściowego (domyślnie: docs/interpelacje.json)"
    )
    parser.add_argument(
        "--kadencja", default="IX",
        help="Kadencja: IX, VIII, VII, VI, V lub 'all' (domyślnie: IX)"
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
