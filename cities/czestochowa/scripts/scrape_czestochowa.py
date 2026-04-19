#!/usr/bin/env python3
"""
Scraper dla Rady Miasta Częstochowy.

Stub wygenerowany przez add_city.py. Zaimplementuj logikę pobierania
protokołów sesji z:
  BIP: https://bip.czestochowa.pl
  eSesja: https://czestochowa.esesja.pl

Konwencja wyjścia:
  docs/data.json       sesje + głosowania w formacie Radoskopa
  docs/profiles.json   profile radnych

Struktura data.json jest zgodna z innymi miastami. Sprawdź
radoskop-premium/radoskop-sopot/scripts/scrape_sopot.py jako referencję.
"""

import argparse
import json
import sys
from pathlib import Path


def scrape(output: Path, profiles: Path, cache_dir: Path, max_sessions: int | None, dry_run: bool) -> None:
    """
    TODO: pobierz listę sesji z eSesji, sparsuj protokoły, zapisz data.json.
    """
    raise NotImplementedError(
        "Scraper dla Częstochowa nie jest jeszcze zaimplementowany.\n"
        "Zacznij od eSesja API: https://czestochowa.esesja.pl"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper Radoskop Częstochowa")
    parser.add_argument("--output", required=True, type=Path, help="Ścieżka do docs/data.json")
    parser.add_argument("--profiles", required=True, type=Path, help="Ścieżka do docs/profiles.json")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"), help="Katalog cache")
    parser.add_argument("--max-sessions", type=int, default=None, help="Ogranicz do N ostatnich sesji")
    parser.add_argument("--dry-run", action="store_true", help="Tylko lista sesji, bez parsowania")
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.profiles.parent.mkdir(parents=True, exist_ok=True)

    try:
        scrape(args.output, args.profiles, args.cache_dir, args.max_sessions, args.dry_run)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
