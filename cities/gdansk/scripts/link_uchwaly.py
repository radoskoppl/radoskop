#!/usr/bin/env python3
"""Link uchwały with votes by matching session numbers and topics.

Reads:
  - data/uchwaly.json (scraped from BAW)
  - docs/data.json (aggregated vote data)

Writes:
  - docs/uchwaly.json (enriched with vote_id links)
"""
import json
import re
import os
from difflib import SequenceMatcher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, "..")

UCHWALY_IN = os.path.join(ROOT_DIR, "data", "uchwaly.json")
DATA_IN = os.path.join(ROOT_DIR, "docs", "data.json")
UCHWALY_OUT = os.path.join(ROOT_DIR, "docs", "uchwaly.json")

MATCH_THRESHOLD = 0.55  # minimum similarity score


def clean_topic(text: str) -> str:
    """Normalize vote topic text for comparison."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip().lower()
    # Remove trailing druk references like "(druk 574);"
    text = re.sub(r'\s*\(druk\s+\d+\)\s*;?\s*$', '', text)
    # Remove leading "w sprawie "
    text = re.sub(r'^w sprawie\s+', '', text)
    return text[:250]


def clean_title(title: str) -> str:
    """Extract comparable part from full uchwała title."""
    if not title:
        return ""
    # Find "w sprawie..." part
    m = re.search(r'w sprawie\s+(.+)', title, re.IGNORECASE)
    if m:
        result = m.group(1)
    else:
        result = title
    return re.sub(r'\s+', ' ', result).strip().lower()[:250]


def get_session_roman(numer: str) -> str | None:
    """Extract session roman numeral from resolution number like XXIV/596/26."""
    parts = numer.split("/")
    return parts[0] if len(parts) >= 2 else None


def determine_kadencja(date: str) -> str | None:
    """Determine kadencja from date string."""
    if not date:
        return None
    kadencje = [
        ("2024-2029", "2024-05-07", "2029-05-06"),
        ("2018-2023", "2018-11-22", "2024-05-06"),
        ("2014-2018", "2014-12-01", "2018-11-21"),
        ("2010-2014", "2010-12-01", "2014-11-30"),
        ("2006-2010", "2006-11-27", "2010-11-30"),
        ("2002-2006", "2002-11-19", "2006-11-26"),
        ("1998-2002", "1998-10-27", "2002-11-18"),
    ]
    for kid, start, end in kadencje:
        if start <= date <= end:
            return kid
    return None


def link():
    """Main linking logic."""
    with open(UCHWALY_IN, encoding="utf-8") as f:
        uchwaly = json.load(f)
    with open(DATA_IN, encoding="utf-8") as f:
        data = json.load(f)

    # Build session → votes map
    sess_votes: dict[str, list] = {}
    for kad in data["kadencje"]:
        for v in kad["votes"]:
            sn = v.get("session_number", "")
            sess_votes.setdefault(sn, []).append(v)

    # Track used votes to prevent double-matching
    used_votes: set[str] = set()
    matched_count = 0
    high_conf = 0

    for u in uchwaly:
        sess_roman = get_session_roman(u["numer"])
        if not sess_roman:
            continue

        votes = sess_votes.get(sess_roman, [])
        if not votes:
            continue

        u_text = clean_title(u.get("tytul", ""))
        if not u_text:
            continue

        best_score = 0.0
        best_vote = None

        for v in votes:
            vid = v.get("id", "")
            if vid in used_votes:
                continue
            v_text = clean_topic(v.get("topic", ""))
            if not v_text:
                continue

            score = SequenceMatcher(None, u_text[:200], v_text[:200]).ratio()
            if score > best_score:
                best_score = score
                best_vote = v

        if best_vote and best_score >= MATCH_THRESHOLD:
            u["vote_id"] = best_vote["id"]
            u["vote_score"] = round(best_score, 3)
            used_votes.add(best_vote["id"])
            matched_count += 1
            if best_score > 0.8:
                high_conf += 1

        # Add kadencja info
        u["kadencja"] = determine_kadencja(u.get("data_podjecia"))

    # Save enriched data
    with open(UCHWALY_OUT, "w", encoding="utf-8") as f:
        json.dump(uchwaly, f, ensure_ascii=False, indent=2)

    # Stats
    statuses = {}
    for u in uchwaly:
        s = u.get("status", "brak")
        statuses[s] = statuses.get(s, 0) + 1

    print(f"Uchwały: {len(uchwaly)}")
    print(f"Matched with votes: {matched_count}")
    print(f"  High confidence (>0.8): {high_conf}")
    print(f"  Medium confidence (0.55-0.8): {matched_count - high_conf}")
    print(f"Unmatched: {len(uchwaly) - matched_count}")
    print(f"\nSaved to: {UCHWALY_OUT}")
    print(f"\nStatus breakdown:")
    for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    return uchwaly


if __name__ == "__main__":
    link()
