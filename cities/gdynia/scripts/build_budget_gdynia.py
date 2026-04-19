#!/usr/bin/env python3
"""Build budget.json for radoskop-gdynia from budget PDF documents + vote data."""
import json
import re
import os
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF required. Install with: pip install PyMuPDF")
    sys.exit(1)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(SCRIPTS_DIR, '..', 'docs')

# --- PDF file configuration ---
# Map each year to its primary budget PDF filename
# These files should be in the same directory or provide full paths
PDF_FILES = {
    2020: 'K2_2020.pdf',
    2021: 'Projekt budżetu i WPF 2021.pdf',
    2022: 'Budżet 2022.pdf',
    2023: 'Projekt 2023.pdf',
    2024: 'Projekt_2024.pdf',
    2025: 'Budżet i WPF 2025.pdf',
    2026: 'Projekt budżetu 2026.pdf',
}

# --- Budget classification mapping (dział → category name) ---
# Consistent with Warszawa's naming for cross-city comparisons
DZIAL_MAP = {
    '010': 'Rolnictwo',
    '020': 'Rolnictwo',       # Leśnictwo → merge into Rolnictwo
    '150': 'Inne',             # Rozwój przedsiębiorczości
    '400': 'Gospodarka komunalna',  # Wytwarzanie energii
    '600': 'Transport',
    '630': 'Inne',             # Turystyka
    '700': 'Gospodarka mieszkaniowa',
    '710': 'Inne',             # Działalność usługowa
    '720': 'Inne',             # Informatyka
    '730': 'Inne',             # Szkolnictwo wyższe i nauka
    '750': 'Administracja',
    '751': 'Administracja',    # Urzędy naczelnych organów
    '752': 'Inne',             # Obrona narodowa
    '753': 'Inne',             # Obowiązkowe ubezpieczenia
    '754': 'Inne',             # Bezpieczeństwo publiczne
    '755': 'Inne',             # Wymiar sprawiedliwości
    '757': 'Obsługa długu',
    '758': 'Inne',             # Różne rozliczenia
    '801': 'Edukacja',
    '851': 'Inne',             # Ochrona zdrowia
    '852': 'Pomoc społeczna',
    '853': 'Pomoc społeczna',  # Pozostałe zadania polityki społecznej
    '854': 'Edukacja',         # Edukacyjna opieka wychowawcza
    '855': 'Rodzina',
    '900': 'Gospodarka komunalna',
    '921': 'Kultura',
    '926': 'Sport',
}


def parse_amount(text):
    """Parse Polish-formatted amount string like '1 234 567,89' to int."""
    if not text or text.strip() == '':
        return 0
    text = text.strip().replace('\xa0', ' ')
    # Remove decimal part (,XX)
    text = re.sub(r',\d+$', '', text)
    # Remove thousand separators (spaces and dots)
    # Polish format: dots for thousands, comma for decimals
    text = text.replace(' ', '').replace('.', '')
    # Handle parentheses (negative numbers)
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        return int(text)
    except ValueError:
        return 0


def extract_totals_from_paragraph(doc):
    """Extract revenue, expenditure, deficit from §1 of the budget resolution."""
    for page_num in range(min(15, len(doc))):
        text = doc[page_num].get_text()

        # Look for the standard budget resolution text
        if 'Ustala się dochody budżetu' not in text:
            continue

        # Extract revenue (dochody)
        m = re.search(
            r'dochody budżetu miasta.*?na kwotę\s+([\d\s.,]+)\s*zł',
            text, re.DOTALL
        )
        revenue = parse_amount(m.group(1)) if m else 0

        # Extract expenditure (wydatki)
        m = re.search(
            r'wydatki budżetu miasta.*?na kwotę\s+([\d\s.,]+)\s*zł',
            text, re.DOTALL
        )
        expenditure = parse_amount(m.group(1)) if m else 0

        # Extract deficit
        m = re.search(
            r'deficyt budżetu w kwocie\s+([\d\s.,]+)\s*zł',
            text, re.DOTALL
        )
        deficit = parse_amount(m.group(1)) if m else 0

        if revenue and expenditure:
            return revenue, expenditure, deficit

    return None, None, None


def find_expenditure_page_range(doc):
    """Find the start and end pages of the expenditure table.

    Strategy: find the page with 'WYDATKI OG' (WYDATKI OGÓŁEM or garbled variant),
    then determine if it's at the start or end of the table, and find the full range.
    """
    wydatki_page = None

    for i in range(min(80, len(doc))):
        text = doc[i].get_text().upper()
        if 'WYDATKI OG' in text:
            # Verify it's in table context (not just §1 text)
            page_text = doc[i].get_text()
            has_codes = any(code in page_text for code in ['010', '600', '700', '750', '801', '926'])
            has_table_hdr = ('Dział' in page_text or 'Dz.' in page_text or
                             'Wyszczególnienie' in page_text)
            if has_codes or has_table_hdr:
                wydatki_page = i
                break

    if wydatki_page is None:
        return None, None

    # Determine if WYDATKI OGÓŁEM is at the start or end of the table
    # by checking the table structure
    wydatki_at_start = False
    tables = doc[wydatki_page].find_tables()
    for table in tables.tables:
        data = table.extract()
        if not data:
            continue
        wydatki_row_idx = None
        for row_idx, row in enumerate(data):
            cell0 = str(row[0] or '').strip().upper()
            if 'WYDATKI OG' in cell0:
                wydatki_row_idx = row_idx
                break
        if wydatki_row_idx is not None:
            # Check if there are dział rows AFTER the WYDATKI row
            for row in data[wydatki_row_idx + 1:]:
                dz = str(row[0] or '').strip()
                if re.match(r'^\d{3}$', dz):
                    wydatki_at_start = True
                    break
            break

    if wydatki_at_start:
        # WYDATKI OGÓŁEM is at the START of the table
        start_page = wydatki_page
        end_page = wydatki_page + 60
    else:
        # WYDATKI OGÓŁEM is at the END of the table
        # Scan backwards to find the start
        end_page = wydatki_page + 1
        start_page = wydatki_page

        for i in range(wydatki_page - 1, max(wydatki_page - 60, -1), -1):
            page_text = doc[i].get_text()
            page_upper = page_text.upper()

            # Stop if we hit the revenue table (has DOCHODY OGÓŁEM)
            if 'DOCHODY OG' in page_upper:
                break

            # Stop if we hit a non-table page (cover, TOC, resolution text)
            if 'Uchwała' in page_text or 'uchwala, co następuje' in page_text:
                break
            if 'SPIS TREŚCI' in page_upper:
                break

            # Check if page has expenditure table format
            # Allow pages without dział codes (they may have only rozdział/§ rows)
            has_table_format = ('Wyszczególnienie' in page_text or
                                'Zadania' in page_text or
                                'Dz' in page_text)

            if has_table_format:
                start_page = i
            else:
                # Page doesn't look like expenditure table, stop
                break

    return start_page, min(end_page, len(doc))


def extract_categories_from_doc(doc):
    """Extract dział-level expenditure totals from the expenditure table."""
    start_page, end_page = find_expenditure_page_range(doc)
    if start_page is None:
        return {}

    print(f"  Expenditure table: pages {start_page+1}-{end_page}")

    dzial_totals = {}
    expenditure_table_cols = None

    # Process from start page through the expenditure table
    for page_idx in range(start_page, end_page):
        tables = doc[page_idx].find_tables()
        for table in tables.tables:
            data = table.extract()
            if not data or len(data) < 2:
                continue

            # Find relevant column indices
            header = data[0]
            ogol_idx = None
            dz_idx = None
            rozdz_idx = None

            for col_idx, cell in enumerate(header):
                cell_str = str(cell or '')
                # Match 'Ogółem' or garbled variants like 'Og my', 'Og em'
                if 'Ogółem' in cell_str or re.match(r'^Og', cell_str):
                    ogol_idx = col_idx
                if re.match(r'Dz', cell_str):
                    dz_idx = col_idx
                if 'Roz' in cell_str or 'rozdz' in cell_str.lower():
                    rozdz_idx = col_idx

            if dz_idx is None:
                continue
            # If Ogółem not found, use last column (it's almost always the total)
            if ogol_idx is None:
                ogol_idx = len(header) - 1

            if expenditure_table_cols is None:
                expenditure_table_cols = len(header)
            # Skip tables with very different column counts (e.g., dotacje section
            # with 4 cols vs expenditure with 9-13 cols), but allow ±4 for
            # "w tym" sub-column variants
            if abs(len(header) - expenditure_table_cols) > 4:
                continue

            # Process rows for dział totals
            for row in data[1:]:
                if len(row) <= max(ogol_idx, dz_idx):
                    continue

                dz_val = str(row[dz_idx] or '').strip()

                # Skip non-dział rows
                if not re.match(r'^\d{3}$', dz_val):
                    continue

                # Check that rozdział is empty (this is a dział total, not a chapter)
                if rozdz_idx is not None and row[rozdz_idx] and str(row[rozdz_idx]).strip():
                    continue

                amount = parse_amount(str(row[ogol_idx] or ''))
                if amount > 0:
                    dzial_totals[dz_val] = dzial_totals.get(dz_val, 0) + amount

    return dzial_totals


def map_dzial_to_categories(dzial_totals):
    """Map dział codes to named categories using DZIAL_MAP."""
    categories = {}
    for code, amount in dzial_totals.items():
        cat_name = DZIAL_MAP.get(code, 'Inne')
        categories[cat_name] = categories.get(cat_name, 0) + amount

    # Sort by amount descending
    result = [{"name": name, "amount": amount}
              for name, amount in sorted(categories.items(), key=lambda x: -x[1])]
    return result


def process_pdf(filepath, year):
    """Process a single budget PDF to extract totals and categories."""
    print(f"\n--- Processing {os.path.basename(filepath)} (year {year}) ---")

    doc = fitz.open(filepath)

    # 1. Extract totals from §1
    revenue, expenditure, deficit = extract_totals_from_paragraph(doc)
    if revenue:
        print(f"  Totals: revenue={revenue:,}, expenditure={expenditure:,}, deficit={deficit:,}")
    else:
        print(f"  WARNING: Could not extract totals from §1!")

    # 2. Extract expenditure categories by dział
    dzial_totals = extract_categories_from_doc(doc)
    categories = []
    if dzial_totals:
        categories = map_dzial_to_categories(dzial_totals)
        cat_total = sum(c['amount'] for c in categories)
        print(f"  Categories: {len(dzial_totals)} działy → {len(categories)} categories, total={cat_total:,}")
        for c in categories:
            print(f"    {c['name']}: {c['amount']:,}")

        # Sanity check
        if expenditure and abs(cat_total - expenditure) > expenditure * 0.05:
            print(f"  WARNING: Category total ({cat_total:,}) differs from expenditure ({expenditure:,}) by {abs(cat_total-expenditure):,}")
    else:
        print(f"  WARNING: Could not find expenditure table!")

    doc.close()

    return {
        'revenue': revenue,
        'expenditure': expenditure,
        'deficit': deficit,
        'categories': categories,
    }


def extract_budget_votes(data_path):
    """Extract budget-related votes from data.json, mapped by budget year."""
    with open(data_path, 'r') as f:
        data = json.load(f)

    budget_votes = {}  # year -> list of vote records

    for kad in data['kadencje']:
        for v in kad['votes']:
            topic = (v.get('topic') or '').lower()
            if 'budżet' not in topic and 'budzet' not in topic:
                continue

            # Match "uchwalenia budżetu ... na XXXX rok" or similar
            m = re.search(r'budżet\w*\s+.*?na\s+(\d{4})\s+rok', topic)
            if not m:
                # Try "budżetu ... za XXXX"
                m = re.search(r'budżet\w*\s+.*?za\s+(\d{4})', topic)
            if not m:
                # Try just "budżetu miasta Gdyni na XXXX"
                m = re.search(r'budżet\w*\s+.*?(\d{4})', topic)
            if m:
                budget_year = int(m.group(1))
                if budget_year < 2015 or budget_year > 2030:
                    continue
                budget_votes.setdefault(budget_year, []).append({
                    "id": v['id'],
                    "topic": v.get('topic', ''),
                    "date": v.get('session_date', ''),
                    "za": (v.get('counts') or {}).get('za', 0),
                    "przeciw": (v.get('counts') or {}).get('przeciw', 0),
                })

    return budget_votes


def main():
    # Determine PDF directory from command-line or default
    if len(sys.argv) > 1:
        pdf_dir = sys.argv[1]
    else:
        # Default: look for PDFs in ../pdfs/ relative to this script
        pdf_dir = os.path.join(SCRIPTS_DIR, '..', 'pdfs')

    if not os.path.isdir(pdf_dir):
        print(f"PDF directory not found: {pdf_dir}")
        print(f"Usage: {sys.argv[0]} <pdf_directory>")
        sys.exit(1)

    print(f"PDF directory: {pdf_dir}")

    # Process each year's PDF
    totals = []
    categories_by_year = {}

    for year in sorted(PDF_FILES.keys()):
        filename = PDF_FILES[year]
        filepath = os.path.join(pdf_dir, filename)

        if not os.path.exists(filepath):
            print(f"\nWARNING: {filename} not found, skipping year {year}")
            continue

        result = process_pdf(filepath, year)

        if result['revenue'] and result['expenditure']:
            entry = {
                "year": year,
                "revenue": result['revenue'],
                "expenditure": result['expenditure'],
                "deficit": result['deficit'] or (result['expenditure'] - result['revenue']),
            }
            # Mark future projects as estimated
            if year >= 2026:
                entry["estimated"] = True
            totals.append(entry)

        if result['categories']:
            categories_by_year[str(year)] = result['categories']

    # Extract budget votes from data.json
    data_json_path = os.path.join(DOCS_DIR, 'data.json')
    budget_votes = {}
    if os.path.exists(data_json_path):
        budget_votes = extract_budget_votes(data_json_path)
        print(f"\nBudget votes found:")
        for y in sorted(budget_votes):
            print(f"  {y}: {len(budget_votes[y])} votes")
    else:
        print(f"\nWARNING: data.json not found at {data_json_path}")

    # Build final structure
    budget_data = {
        "totals": totals,
        "categories": categories_by_year,
        "votes": {str(y): votes for y, votes in sorted(budget_votes.items())},
    }

    out_path = os.path.join(DOCS_DIR, 'budget.json')
    with open(out_path, 'w') as f:
        json.dump(budget_data, f, ensure_ascii=False)

    print(f"\nWritten {out_path}")
    print(f"  {len(totals)} years of totals")
    print(f"  {len(categories_by_year)} years of category breakdowns")
    print(f"  {len(budget_votes)} years with budget votes")


if __name__ == '__main__':
    main()
