"""
Parser transkrypcji stenogramu sesji Rady m.st. Warszawy.

Obsługuje pliki DOCX (wersja_tekstowa) i PDF (fallback via PyMuPDF).
Wyciąga dane mówców: imię i nazwisko, liczbę wypowiedzi i słów.

Zależności:
  pip install python-docx pymupdf

Format wejścia:
  Pogrubiony tekst z rolą i nazwiskiem, np.:
    "Radny Wojciech Zabłocki:" — tekst wypowiedzi...
    "Przewodnicząca Rady m.st. Warszawy Ewa Malinowska-Grupińska:" — tekst...

Format wyjścia:
  [{"name": "Wojciech Zabłocki", "statements": 5, "words": 1234}, ...]
"""

import re
from pathlib import Path

# Prefiksy ról do usunięcia (zostawiamy samo imię i nazwisko)
ROLE_PREFIXES = [
    r"Przewodnicząc[ay] Rady m\.st\. Warszawy\s+",
    r"Wiceprzewodnicząc[ay] Rady m\.st\. Warszawy\s+",
    r"Prezydent m\.st\. Warszawy\s+",
    r"Zastępc[ay] Prezydenta m\.st\. Warszawy\s+",
    r"Sekretarz m\.st\. Warszawy\s+",
    r"Skarbnik m\.st\. Warszawy\s+",
    r"Radn[ay]\s+",
    # Dyrektorzy, naczelnicy, etc. — multi-word titles before name
    r"(?:Stołeczn[a-z]+ Konserwator[a-z]* Zabytków|p\.o\. (?:Stołeczn[a-z]+ Konserwator[a-z]* Zabytków))\s+",
    r"Dyrektor(?:ka)?\s+(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+)+",
    r"Zastępc[ay] Dyrektor[a-z]*\s+(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+)+",
    r"Burmistrz(?:yni)?\s+(?:Dzielnicy\s+)?(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\s+)*",
    r"Zastępc[ay] Burmistrz[a-z]*\s+(?:Dzielnicy\s+)?(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\s+)*",
    r"Naczelnik(?:czka)?\s+(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+)+",
    # Catch-all: any title ending in a known pattern before a capitalized name
    r"(?:Pełnomocni[a-z]+|Komendant[a-z]*|Rzeczni[a-z]+)\s+(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+)*",
]

# Kompiluj regex do ekstrakcji nazwy mówcy
ROLE_RE = re.compile("|".join(f"(?:{p})" for p in ROLE_PREFIXES))


def normalize_ws(s: str) -> str:
    """Normalizuj białe znaki — zamień wielokrotne spacje/newline na jedną spację."""
    return re.sub(r"\s+", " ", s).strip()


def extract_name(speaker_label: str) -> str:
    """Wyciągnij imię i nazwisko z etykiety mówcy, usuwając rolę."""
    label = normalize_ws(speaker_label.strip().rstrip(":"))
    # Próbuj usunąć znany prefiks
    cleaned = ROLE_RE.sub("", label, count=1).strip()
    if cleaned and cleaned != label:
        return cleaned
    # Fallback: jeśli żaden prefiks nie pasuje, zwróć całość
    return label


def count_words(text: str) -> int:
    """Policz słowa w tekście."""
    return len(text.split())


def parse_docx(path: str) -> list[dict]:
    """Parsuj transkrypcję DOCX — wykrywaj pogrubione etykiety mówców."""
    from docx import Document
    doc = Document(path)

    speakers = {}  # name -> {"statements": int, "words": int}
    current_speaker = None
    current_words = 0

    for para in doc.paragraphs:
        # Szukaj pogrubionych fragmentów kończących się ":"
        bold_text = ""
        rest_text = ""
        found_colon = False

        for run in para.runs:
            if run.bold and not found_colon:
                bold_text += run.text
                if ":" in run.text:
                    found_colon = True
                    # Część po ":" to już tekst wypowiedzi
                    parts = run.text.split(":", 1)
                    bold_text = bold_text[: bold_text.rfind(":")] if ":" in bold_text else bold_text
                    rest_text += parts[1] if len(parts) > 1 else ""
            else:
                rest_text += run.text

        bold_text = bold_text.strip()

        # Czy to nowy mówca?
        if bold_text and found_colon and len(bold_text) > 5:
            # Zamknij poprzedniego mówcę
            if current_speaker:
                speakers[current_speaker]["words"] += current_words

            name = extract_name(bold_text)
            current_speaker = name
            current_words = count_words(rest_text)

            if name not in speakers:
                speakers[name] = {"statements": 0, "words": 0}
            speakers[name]["statements"] += 1
        else:
            # Kontynuacja wypowiedzi
            full_text = (bold_text + " " + rest_text).strip() if bold_text else rest_text.strip()
            current_words += count_words(full_text)

    # Zamknij ostatniego mówcę
    if current_speaker:
        speakers[current_speaker]["words"] += current_words

    speakers = _merge_speakers(speakers)

    # Konwertuj na posortowaną listę
    result = [
        {"name": name, "statements": data["statements"], "words": data["words"]}
        for name, data in speakers.items()
        if data["statements"] > 0
    ]
    result.sort(key=lambda x: x["words"], reverse=True)
    return result


def _merge_speakers(speakers: dict) -> dict:
    """Połącz warianty tego samego mówcy (skróty imion, resztki ról)."""
    # 1. Mapuj skróty → pełne imiona (np. "E. Malinowska" → "Ewa Malinowska")
    full_names = {}  # nazwisko → pełne imię+nazwisko
    for name in speakers:
        parts = name.split()
        if len(parts) >= 2 and not parts[0].endswith("."):
            surname = parts[-1]
            full_names[surname] = name

    merged = {}
    for name, data in speakers.items():
        parts = name.split()
        # Skrót imienia: "E. Malinowska-Grupińska"
        if len(parts) >= 2 and parts[0].endswith(".") and parts[-1] in full_names:
            target = full_names[parts[-1]]
            if target != name:
                if target not in merged:
                    merged[target] = {"statements": 0, "words": 0}
                merged[target]["statements"] += data["statements"]
                merged[target]["words"] += data["words"]
                continue
        # Filtruj resztki ról (zaczynają się małą literą lub zawierają "obowiązki", "Państwa")
        if (name[0].islower() or
            any(x in name for x in ["obowiązki", "Państwa", "Społecznych", "Obywatelskich",
                                     "Przestrzennego", "Prawny Biura", "Projektów"])):
            # To resztka roli — spróbuj wyłuskać nazwisko na końcu
            # Szukaj ostatniego "Imię Nazwisko" w ciągu
            name_match = re.search(r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:[- ][A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)+)$", name)
            if name_match:
                clean = name_match.group(1)
                if clean not in merged:
                    merged[clean] = {"statements": 0, "words": 0}
                merged[clean]["statements"] += data["statements"]
                merged[clean]["words"] += data["words"]
                continue

        if name not in merged:
            merged[name] = {"statements": 0, "words": 0}
        merged[name]["statements"] += data["statements"]
        merged[name]["words"] += data["words"]

    return merged


def parse_pdf(path: str) -> list[dict]:
    """Parsuj transkrypcję PDF — fallback gdy brak DOCX.

    Używa PyMuPDF (fitz) zamiast pdftotext — nie wymaga systemowego binarki.
    Instalacja: pip install pymupdf
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "Zainstaluj PyMuPDF: pip install pymupdf\n"
            "(Alternatywnie: brew install poppler && pip install pdftotext)"
        )

    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()

    # Wzorzec: linia zaczynająca się od roli/tytułu + nazwisko + ":"
    speaker_re = re.compile(
        r"^((?:Przewodnicząc[ay]|Wiceprzewodnicząc[ay]|Prezydent|Zastępc[ay] Prezydenta|"
        r"Sekretarz|Skarbnik|Radn[ay]|Dyrektor(?:ka)?|Naczelnik(?:czka)?|Burmistrz(?:yni)?|"
        r"Zastępc[ay] (?:Dyrektor|Burmistrz)|Stołeczn[a-z]+ Konserwator|"
        r"Pełnomocni[a-z]+|Komendant[a-z]*|Rzeczni[a-z]+)"
        r"[^:]{3,80}:)\s*(.*)$",
        re.MULTILINE
    )

    speakers = {}
    segments = []

    # Znajdź wszystkie wystąpienia mówców
    for m in speaker_re.finditer(text):
        segments.append((m.start(), m.group(1), m.group(2)))

    for i, (pos, label, first_line) in enumerate(segments):
        name = extract_name(normalize_ws(label))
        # Tekst do następnego mówcy
        end_pos = segments[i + 1][0] if i + 1 < len(segments) else len(text)
        speech = first_line + " " + text[pos + len(label) + len(first_line):end_pos]
        words = count_words(speech)

        if name not in speakers:
            speakers[name] = {"statements": 0, "words": 0}
        speakers[name]["statements"] += 1
        speakers[name]["words"] += words

    speakers = _merge_speakers(speakers)

    result = [
        {"name": name, "statements": data["statements"], "words": data["words"]}
        for name, data in speakers.items()
        if data["statements"] > 0
    ]
    result.sort(key=lambda x: x["words"], reverse=True)
    return result


def parse_transcript(path: str) -> list[dict]:
    """Parsuj transkrypcję — auto-detect DOCX/PDF."""
    p = Path(path)
    if p.suffix.lower() == ".docx":
        return parse_docx(path)
    elif p.suffix.lower() == ".pdf":
        return parse_pdf(path)
    else:
        raise ValueError(f"Nieobsługiwany format: {p.suffix}")


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Użycie: python parse_stenogram.py <plik.docx|plik.pdf>")
        sys.exit(1)

    speakers = parse_transcript(sys.argv[1])
    print(json.dumps(speakers, ensure_ascii=False, indent=2))
    print(f"\nŁącznie: {len(speakers)} mówców, "
          f"{sum(s['statements'] for s in speakers)} wypowiedzi, "
          f"{sum(s['words'] for s in speakers)} słów")
