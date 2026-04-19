# Radoskop Łódź — Scrapers

Скраперы для danych głosowań i interpelacji Rady Miasta Łodzi.

## Instalacja zależności

```bash
pip install requests beautifulsoup4 lxml pymupdf
```

## Scraper głosowań (`scrape_lodz.py`)

Pobiera dane głosowań z PDF-ów dostępnych w BIP Łódź:
- https://bip.uml.lodz.pl/wladze/rada-miejska-w-lodzi/wyniki-glosowan-z-sesji-rady-miejskiej-w-lodzi-ix-kadencji/
- https://bip.uml.lodz.pl/wladze/rada-miejska-w-lodzi/wyniki-glosowan-z-sesji-rady-miejskiej-w-lodzi-viii-kadencji/

### Użycie

```bash
./scrape.sh                                    # Domyślnie
./scrape.sh --output docs/data.json            # Zmień ścieżkę
python3 scripts/scrape_lodz.py --help          # Więcej opcji
```

### Wynik

Generuje `docs/data.json` z strukturą:
```json
{
  "meta": {
    "generated": "2026-03-14T...",
    "version": "1.0"
  },
  "kadencje": [
    {
      "id": "2024-2029",
      "label": "IX kadencja (2024–2029)",
      "councilors": [
        {
          "name": "Imię Nazwisko",
          "club": "KO",
          "votes_za": 10,
          "votes_przeciw": 2,
          "votes_wstrzymal": 1,
          "votes_brak": 0,
          "votes_total": 13,
          "frekwencja": 100.0,
          "aktywnosc": 0.0,
          "zgodnosc_z_klubem": 95.2,
          ...
        }
      ],
      "votes": [
        {
          "id": "v00001",
          "session_number": "VI",
          "session_date": "2024-06-15",
          "subject": "Uchwała w sprawie...",
          "named_votes": {
            "za": ["Imię Nazwisko", ...],
            "przeciw": [],
            "wstrzymal_sie": [],
            "brak_glosu": []
          }
        }
      ]
    }
  ]
}
```

oraz `docs/profiles.json` z profilami radnych.

## Scraper interpelacji (`scrape_interpelacje.py`)

Pobiera listę interpelacji i zapytań radnych z BIP Łódź:
- https://bip.uml.lodz.pl/wladze/rada-miejska-w-lodzi/interpelacje-i-zapytania-radnych/

### Użycie

```bash
./scrape_interpelacje.sh                           # Domyślnie
./scrape_interpelacje.sh --skip-details            # Szybciej, bez szczegółów
./scrape_interpelacje.sh --kadencja IX,VIII        # Wybrane kadencje
./scrape_interpelacje.sh --debug                   # Debugowanie
python3 scripts/scrape_interpelacje.py --help      # Więcej opcji
```

### Wynik

Generuje `docs/interpelacje.json`:
```json
[
  {
    "przedmiot": "Interpelacja w sprawie...",
    "typ": "interpelacja",
    "radny": "Imię Nazwisko",
    "status": "udzielono odpowiedź",
    "kategoria": "transport",
    "bip_url": "https://bip.uml.lodz.pl/...",
    "data_wplywu": "2024-06-15",
    "data_odpowiedzi": "2024-06-30",
    "tresc_url": "https://...",
    "odpowiedz_url": "https://...",
    "nr_sprawy": "...",
    "kadencja": "IX",
    "zalaczniki": [
      {"nazwa": "Treść", "url": "https://..."}
    ]
  }
]
```

## Konfiguracja radnych

Aktualna konfiguracja w `scrape_lodz.py` zawiera template:

```python
COUNCILORS = {
    # KO - Koalicja Obywatelska
    "Radny KO 1": "KO",
    ...
    # PiS - Prawo i Sprawiedliwość
    "Radny PiS 1": "PiS",
    ...
}
```

**TODO:** Pobierz pełną listę radnych z:
https://bip.uml.lodz.pl/wladze/rada-miejska-w-lodzi/radni-rady-miejskiej-w-lodzi-ix-kadencji/

i kluby radnych z:
https://bip.uml.lodz.pl/wladze/rada-miejska-w-lodzi/kluby-radnych-ix-kadencji/

Nazwy muszą **dokładnie pasować** do formy w PDF-ach (Imię Nazwisko, z polskimi znakami).

## Kluby radnych

Dla kadencji IX (2024-2029):
- **KO** — Koalicja Obywatelska
- **PiS** — Prawo i Sprawiedliwość
- **Lewica**
- **TD** — Trzecia Droga

## Uwagi

- **UWAGA:** Oba skrypty wymagają dostępu do internetu (domyślnie localhost)
- Skrypt pobiera PDF-y jednocześnie, co może być powolne — zmień `DELAY` w kodzie
- Interpelacje są klasyfikowane automatycznie na kategorie (transport, infrastruktura, etc.)
- Daty są konwertowane do formatu YYYY-MM-DD

## Debugowanie

```bash
python3 scripts/scrape_lodz.py --debug 2>&1 | less
python3 scripts/scrape_interpelacje.py --debug 2>&1 | less
```
