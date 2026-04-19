#!/usr/bin/env python3
"""Scrape uchwały Rady Miasta Gdańska from BAW (Baza Aktów Własnych).

Uses the discovered API endpoint: POST /api/documents/GetDocumentsNewGrid
Fetches all resolutions in batches of 50 and saves as JSON.

BAW parameters for Gdańsk:
  InstitutionId: 216
  AdditionalId (bagId): 1200  (Zbiór uchwał Rady Miasta Gdańska)
"""
import json
import time
import sys
import os
import requests

BAW_BASE = "https://baw.bip.gdansk.pl"
API_URL = f"{BAW_BASE}/api/documents/GetDocumentsNewGrid"
INSTITUTION_ID = 216
BAG_ID = 1200  # Zbiór uchwał Rady Miasta Gdańska

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
OUTPUT = os.path.join(DATA_DIR, "uchwaly.json")

BATCH_SIZE = 50
DELAY = 0.1  # seconds between requests


def make_payload(skip: int, take: int) -> dict:
    """Create the POST payload for the BAW API."""
    return {
        "pageNumber": 0,
        "pageSize": take,
        "isBlocked": True,
        "searchText": "",
        "searchInContentWithElasticSearch": False,
        "hideAmendingActs": False,
        "SearchText": "",
        "Asc": 1,
        "ColumnId": -1,
        "InstitutionId": INSTITUTION_ID,
        "PageNumber": 0,
        "PageSize": take,
        "SearchTextInPdf": False,
        "DevExtremeGridOptions": {
            "sort": None,
            "group": None,
            "searchOperation": "contains",
            "searchValue": None,
            "skip": skip,
            "take": take,
            "userData": {}
        },
        "AdditionalId": BAG_ID,
        "SearchForType": 0
    }


def parse_document(doc: dict) -> dict:
    """Transform a raw API document into a clean record."""
    status = doc.get("LegalActStatus", {})
    pub_addr = doc.get("PublishAddress") or {}
    bodies = doc.get("LegislativeBodies") or []

    return {
        "id": doc.get("Id"),
        "numer": doc.get("ActNumber"),
        "numer_sort": doc.get("ActNumberComputed"),
        "typ": doc.get("LegalActTypeDescription", "Uchwała"),
        "data_podjecia": (doc.get("ActDate") or "")[:10] or None,
        "data_publikacji": (doc.get("PublishedDate") or "")[:10] or None,
        "data_wejscia": (doc.get("ValidFrom") or "")[:10] or None,
        "status": status.get("Name") if isinstance(status, dict) else None,
        "tytul": (doc.get("Subject") or "").replace("\r\n", " ").replace("\r", " ").strip() or None,
        "organ": bodies[0]["Name"] if bodies else "Rada Miasta Gdańska",
        "odpowiedzialny": doc.get("ResponsibleNames"),
        "poz_dz_urz": pub_addr.get("Position"),
        "rok_dz_urz": pub_addr.get("Year"),
    }


def scrape_uchwaly():
    """Fetch all uchwały from BAW API."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # First request to get total count
    print(f"Connecting to {BAW_BASE}...")
    payload = make_payload(skip=0, take=1)
    r = session.post(API_URL, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    dex = data.get("DevExtremeDocuments") or {}
    total_count = dex.get("totalCount", 0)
    if not total_count:
        print("ERROR: Could not determine total count.")
        print(f"Response keys: {list(data.keys())}")
        sys.exit(1)

    print(f"Total uchwał: {total_count}")
    total_batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE

    all_docs = []
    for batch in range(total_batches):
        skip = batch * BATCH_SIZE
        payload = make_payload(skip=skip, take=BATCH_SIZE)

        try:
            r = session.post(API_URL, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            dex = data.get("DevExtremeDocuments") or {}
            docs = dex.get("data", [])

            for doc in docs:
                all_docs.append(parse_document(doc))

        except Exception as e:
            print(f"  [!] Batch {batch} (skip={skip}) error: {e}")

        if (batch + 1) % 20 == 0 or batch == total_batches - 1:
            print(f"  [{batch+1}/{total_batches}] Collected: {len(all_docs)}")

        time.sleep(DELAY)

    return all_docs


def save_results(docs: list):
    """Save results to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Sort by date descending
    docs.sort(key=lambda x: x.get("data_podjecia") or "", reverse=True)

    # Remove duplicates (by numer)
    seen = set()
    unique = []
    for d in docs:
        if d["numer"] not in seen:
            seen.add(d["numer"])
            unique.append(d)

    print(f"\nTotal uchwał: {len(docs)}, unique: {len(unique)}")

    # Save full dataset
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT}")

    # Print summary stats
    statuses = {}
    years = {}
    for d in unique:
        s = d.get("status", "brak")
        statuses[s] = statuses.get(s, 0) + 1
        y = (d.get("data_podjecia") or "????")[:4]
        years[y] = years.get(y, 0) + 1

    print("\nStatus breakdown:")
    for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    print("\nPer year (last 10):")
    for y in sorted(years.keys(), reverse=True)[:10]:
        print(f"  {y}: {years[y]}")

    return unique


if __name__ == "__main__":
    docs = scrape_uchwaly()
    save_results(docs)
