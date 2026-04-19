#!/usr/bin/env python3
"""
Debug helper for interpelacje scraper.
Saves raw HTML response to file for inspection.

Usage:
  python3 debug_interpelacje.py [--year 2025] [--type interpelacje]
"""

import argparse
import requests
import json
from bs4 import BeautifulSoup

INTERP_URL = "https://bip.gdansk.pl/picklock/publikacja-interpelacji-radnych-miasta-gdanska"
ZAP_URL = "https://bip.gdansk.pl/picklock/publikacja-zapytan-radnych-miasta-gdanska"

HEADERS = {
    "User-Agent": "Radoskop/1.0 (https://gdansk.radoskop.pl; kontakt@radoskop.pl)"
}


def debug_fetch(typ, year):
    """Fetch and analyze response."""
    url = INTERP_URL if typ == "interpelacje" else ZAP_URL
    print(f"Fetching {typ} for year {year}...")
    print(f"URL: {url}")

    session = requests.Session()

    # GET with picklock endpoint
    print(f"\n=== Fetching (GET /picklock/?rok={year}) ===")
    params = {"rok": str(year), "wyszukiwana_tresc": ""}
    resp = session.get(url, params=params, headers=HEADERS, timeout=120)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    print(f"Length: {len(resp.text)} bytes")

    # Analysis
    print(f"\n=== Step 3: Analysis ===")

    # Check if JSON
    try:
        data_json = resp.json()
        print("Response is JSON!")
        print(f"JSON keys: {list(data_json.keys()) if isinstance(data_json, dict) else 'array'}")
        print(f"JSON preview: {json.dumps(data_json, indent=2, ensure_ascii=False)[:500]}")
        return
    except:
        pass

    # Parse as HTML
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all tables
    all_tables = soup.find_all("table")
    print(f"Total tables found: {len(all_tables)}")

    # Find tables with specific classes
    table_classes = {}
    for table in all_tables:
        cls = table.get("class")
        cls_str = " ".join(cls) if cls else "(no class)"
        table_classes[cls_str] = table_classes.get(cls_str, 0) + 1

    print(f"Table classes found:")
    for cls, count in sorted(table_classes.items(), key=lambda x: -x[1]):
        print(f"  '{cls}': {count} tables")

    # Look for table-sm specifically
    table_sm = soup.find_all("table", class_="table-sm")
    print(f"\nTables with class='table-sm': {len(table_sm)}")

    # Show first table structure
    if all_tables:
        print(f"\n=== First table structure ===")
        first_table = all_tables[0]
        print(f"Tag: {first_table.name}")
        print(f"Attributes: {first_table.attrs}")

        # Show rows and cells
        rows = first_table.find_all("tr")
        print(f"Rows: {len(rows)}")
        if rows:
            first_row = rows[0]
            cells = first_row.find_all(["td", "th"])
            print(f"First row cells: {len(cells)}")
            for i, cell in enumerate(cells[:3]):
                print(f"  Cell {i}: {cell.name} = '{cell.get_text(strip=True)[:50]}'")

    # Save raw HTML
    output_file = f"/tmp/bip_gdansk_{typ}_{year}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"\n✓ Saved raw HTML to: {output_file}")

    # Save first 2000 chars
    preview_file = f"/tmp/bip_gdansk_{typ}_{year}_preview.txt"
    with open(preview_file, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n")
        f.write(f"Year: {year}\n")
        f.write(f"Status: {resp.status_code}\n")
        f.write(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}\n")
        f.write(f"Length: {len(resp.text)} bytes\n")
        f.write(f"\n=== Response Preview ===\n")
        f.write(resp.text[:2000])
    print(f"✓ Saved preview to: {preview_file}")


def main():
    parser = argparse.ArgumentParser(description="Debug interpelacje scraper")
    parser.add_argument("--year", type=int, default=2025, help="Year to fetch")
    parser.add_argument("--type", choices=["interpelacje", "zapytania"],
                       default="interpelacje", help="Type to fetch")
    args = parser.parse_args()

    try:
        debug_fetch(args.type, args.year)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
