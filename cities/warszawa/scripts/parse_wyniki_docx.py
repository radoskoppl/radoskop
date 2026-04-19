#!/usr/bin/env python3
"""
Parser plików wyniki_glosowania_*.docx z BIP Warszawa.

Struktura dokumentu:
  - Paragraph: tytuł sesji (np. "Głosowanie z XXXII sesji...")
  - Paragraph: temat głosowania (zaczyna się od "–")
  - Opcjonalny paragraph z wynikami liczbowymi (Za: X, Przeciw: Y...)
  - Table: lista radnych "ZA" (domyślna kategoria po temacie)
  - Paragraph "PRZECIW:" → Table: lista radnych przeciw
  - Paragraph "WSTRZYMUJĘ SIĘ:" → Table: lista wstrzymujących się

Użycie:
    python parse_wyniki_docx.py plik.docx [--output votes.json]
"""

import json
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError:
    print("Zainstaluj: pip install python-docx")
    sys.exit(1)


def extract_names_from_table(tbl) -> list[str]:
    """Wyciągnij nazwiska z tabeli (4 kolumny, wiele wierszy)."""
    names = []
    for tr in tbl.findall(qn("w:tr")):
        for tc in tr.findall(qn("w:tc")):
            texts = [t.text or "" for t in tc.iter(qn("w:t"))]
            name = "".join(texts).strip()
            # Zamień non-breaking space na zwykłą spację
            name = name.replace("\xa0", " ")
            if name and len(name) > 2:
                names.append(name)
    return names


def get_para_text(p_el) -> str:
    """Wyciągnij tekst z elementu paragrafu XML."""
    texts = [t.text or "" for t in p_el.iter(qn("w:t"))]
    return "".join(texts).strip()


def parse_docx(filepath: str) -> list[dict]:
    """Parsuj plik wyniki_glosowania_*.docx → lista głosowań."""
    doc = Document(filepath)
    body = doc.element.body
    elements = list(body)

    votes = []
    i = 0
    current_vote = None

    while i < len(elements):
        el = elements[i]
        tag = el.tag.split("}")[-1]

        if tag == "p":
            text = get_para_text(el)

            if not text:
                i += 1
                continue

            # Nagłówek kategorii
            text_lower = text.lower().strip()
            if text_lower.startswith("przeciw"):
                # Następna tabela to lista PRZECIW
                if current_vote and i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["przeciw"] = extract_names_from_table(next_el)
                        i += 2
                        continue
                i += 1
                continue

            if "wstrzymuj" in text_lower:
                # Następna tabela to lista WSTRZYMUJĄCYCH SIĘ
                if current_vote and i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["wstrzymal_sie"] = extract_names_from_table(next_el)
                        i += 2
                        continue
                i += 1
                continue

            if "nie głosował" in text_lower or "brak głosu" in text_lower:
                if current_vote and i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["brak_glosu"] = extract_names_from_table(next_el)
                        i += 2
                        continue
                i += 1
                continue

            if "nieobecn" in text_lower:
                if current_vote and i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["nieobecni"] = extract_names_from_table(next_el)
                        i += 2
                        continue
                i += 1
                continue

            # Nagłówek "ZA:" — explicite oznaczona lista ZA
            if text_lower in ("za:", "za"):
                if current_vote and i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["za"] = extract_names_from_table(next_el)
                        i += 2
                        continue
                i += 1
                continue

            # Nowy temat głosowania:
            # - zaczyna się od "–", "—", "- ", "−" (wnioski)
            # - zaczyna się od "Uchwała Nr" (przyjęte uchwały)
            # - zaczyna się od "Projekt uchwały" lub "Projekt stanowiska"
            # Pomiń standalone "Radni głosowali..." — to wyniki, nie temat
            if text_lower.startswith("radni głosowali"):
                i += 1
                continue

            is_vote_topic = (
                text.startswith("–") or text.startswith("—") or
                text.startswith("- ") or text.startswith("−") or
                text.startswith("Uchwała Nr") or
                text.startswith("Projekt uchwały") or
                text.startswith("Projekt stanowiska") or
                text.startswith("Przyjęcie protokołu") or
                text.startswith("Stanowisko nr")
            )
            if is_vote_topic:
                # Odetnij wyniki głosowania z tematu ("Radni głosowali..." i dalej)
                cut = re.search(r"Radni głosowali", text)
                if cut:
                    text = text[:cut.start()].rstrip()
                # Zapisz poprzednie głosowanie
                if current_vote:
                    finalize_vote(current_vote)
                    votes.append(current_vote)

                # Wyciągnij numer druku
                druk = None
                druk_match = re.search(r"druk\s*(?:nr\s*)?(\d+[A-Z]?)", text, re.I)
                if druk_match:
                    druk = druk_match.group(1)

                # Parsuj wyniki liczbowe z tekstu
                counts = parse_counts_from_text(text)

                # Wyczyść temat: nbsp → spacja, leading dash
                clean_topic = text.replace("\xa0", " ").strip()
                if clean_topic.startswith(("– ", "— ", "- ", "− ")):
                    clean_topic = clean_topic[2:].strip()
                elif clean_topic.startswith(("–", "—", "-", "−")):
                    clean_topic = clean_topic[1:].strip()

                current_vote = {
                    "topic": clean_topic,
                    "druk": druk,
                    "counts_declared": counts,
                    "named_votes": {
                        "za": [],
                        "przeciw": [],
                        "wstrzymal_sie": [],
                        "brak_glosu": [],
                        "nieobecni": [],
                    },
                }

                # Sprawdź czy następny element to tabela (lista ZA)
                if i + 1 < len(elements):
                    next_el = elements[i + 1]
                    if next_el.tag.split("}")[-1] == "tbl":
                        current_vote["named_votes"]["za"] = extract_names_from_table(next_el)
                        i += 2
                        continue

        elif tag == "tbl":
            # Tabela bez kontekstu — prawdopodobnie ZA po temacie
            # (już obsłużone powyżej)
            pass

        i += 1

    # Zapisz ostatnie głosowanie
    if current_vote:
        finalize_vote(current_vote)
        votes.append(current_vote)

    return votes


def parse_counts_from_text(text: str) -> dict:
    """Wyciągnij zadeklarowane liczby głosów z tekstu."""
    counts = {}
    za_match = re.search(r"Za:\s*(\d+)", text)
    if za_match:
        counts["za"] = int(za_match.group(1))
    przeciw_match = re.search(r"Przeciw:\s*(\d+)", text)
    if przeciw_match:
        counts["przeciw"] = int(przeciw_match.group(1))
    wstrzymal_match = re.search(r"Wstrzymał[ao]?\s*się:\s*(\d+)", text)
    if wstrzymal_match:
        counts["wstrzymal_sie"] = int(wstrzymal_match.group(1))
    return counts


def finalize_vote(vote: dict):
    """Dodaj policzone counts z list imiennych, deduplikuj cross-category."""
    nv = vote["named_votes"]
    # Deduplikacja: pierwsza tabela po temacie bywa pełną listą głosujących,
    # a nie tylko "za". Kategorie z explicite nagłówków (PRZECIW:, WSTRZYMUJĘ SIĘ: itd.)
    # mają priorytet — usuwamy z "za" osoby które są w bardziej specyficznych listach.
    others = set(nv["przeciw"]) | set(nv["wstrzymal_sie"]) | set(nv["brak_glosu"])
    if others & set(nv["za"]):
        nv["za"] = [n for n in nv["za"] if n not in others]
    vote["counts"] = {
        "za": len(nv["za"]),
        "przeciw": len(nv["przeciw"]),
        "wstrzymal_sie": len(nv["wstrzymal_sie"]),
        "brak_glosu": len(nv["brak_glosu"]),
        "nieobecni": len(nv["nieobecni"]),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parser wyników głosowań z docx")
    parser.add_argument("docx_file", help="Ścieżka do pliku .docx")
    parser.add_argument("--output", "-o", help="Plik wyjściowy JSON")
    args = parser.parse_args()

    votes = parse_docx(args.docx_file)

    print(f"Sparsowano {len(votes)} głosowań")
    for i, v in enumerate(votes):
        za = v["counts"]["za"]
        przeciw = v["counts"]["przeciw"]
        wstrzym = v["counts"]["wstrzymal_sie"]
        topic = v["topic"][:80]
        druk = f" (druk {v['druk']})" if v["druk"] else ""
        print(f"  {i+1:2}. Za:{za} Przeciw:{przeciw} Wstrzym:{wstrzym}{druk} — {topic}")

    if args.output:
        Path(args.output).write_text(
            json.dumps(votes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nZapisano → {args.output}")


if __name__ == "__main__":
    main()
