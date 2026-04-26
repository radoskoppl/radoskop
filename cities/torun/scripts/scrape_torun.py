#!/usr/bin/env python3
"""
Radoskop Toruń — STUB scraper.

This council does not use eSesja. A custom BIP scraper needs to be written
(see lib_bip_static.py — subclass BipScraper, implement discover_sessions()
and parse_session_votes()). Until then this stub emits valid-but-empty
outputs so downstream generators don't crash. The city appears on
radoskop.pl with population + link to BIP, no per-session data.

BIP URL: https://www.bip.torun.pl/
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from lib_esesja import _write_empty_outputs

KADENCJE = {
    "2024-2029": {"label": "IX kadencja (2024–2029)", "start": "2024-05-07"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Radoskop Toruń (stub)")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--max-sessions", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("[Toruń] stub scraper — writing empty valid outputs.")
    _write_empty_outputs(args.output, args.profiles, KADENCJE, "2024-2029")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
