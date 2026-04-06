#!/usr/bin/env python3
"""
Generate "Mój radny" (Find your councilor) page for each city.
"""
import json
import argparse
import os
from pathlib import Path


def get_latest_kadencja(profiles_data):
    """Get the latest kadencja ID from profiles data."""
    if not profiles_data.get('profiles'):
        return None

    first_profile = profiles_data['profiles'][0]
    kadencje_ids = sorted(list(first_profile.get('kadencje', {}).keys()))
    return kadencje_ids[-1] if kadencje_ids else None


def generate_html(city_config, profiles_data, city_path):
    """Generate the Mój radny HTML page."""

    city_name = city_config.get('city_name', 'Unknown')
    city_genitive = city_config.get('city_genitive', city_name)
    site_url = city_config.get('site_url', '')
    clubs = city_config.get('clubs', {})

    # Get latest kadencja
    latest_kadencja = get_latest_kadencja(profiles_data)
    if not latest_kadencja:
        print(f"Warning: No kadencja found for {city_name}")
        return None

    profiles = profiles_data.get('profiles', [])

    # Filter profiles for the latest kadencja
    councilors = []
    for profile in profiles:
        kadencje = profile.get('kadencje', {})
        if latest_kadencja in kadencje:
            kadencja_data = kadencje[latest_kadencja]
            if not kadencja_data.get('former', False):  # Exclude former councilors
                councilors.append({
                    'name': profile.get('name', ''),
                    'slug': profile.get('slug', ''),
                    'club': kadencja_data.get('club', ''),
                    'club_full': kadencja_data.get('club_full', ''),
                    'frekwencja': kadencja_data.get('frekwencja', 0),
                    'aktywnosc': kadencja_data.get('aktywnosc', 0),
                    'zgodnosc_z_klubem': kadencja_data.get('zgodnosc_z_klubem', 0),
                    'rebellion_count': kadencja_data.get('rebellion_count', 0),
                    'rebellions': kadencja_data.get('rebellions', [])[:3],
                    'votes_za': kadencja_data.get('votes_za', 0),
                    'votes_przeciw': kadencja_data.get('votes_przeciw', 0),
                    'votes_wstrzymal': kadencja_data.get('votes_wstrzymal', 0),
                })

    # Sort by name
    councilors.sort(key=lambda x: x['name'])

    # Get unique clubs
    unique_clubs = sorted(set(c['club'] for c in councilors if c['club']))

    # Generate club colors CSS
    club_styles = []
    for club in unique_clubs:
        if club in clubs:
            club_data = clubs[club]
            color = club_data.get('color', '#999')
            bg = club_data.get('bg', 'rgba(99,102,241,0.12)')
            club_styles.append(f"""
.club-{club} {{ background: {bg}; color: {color}; }}
.avatar-{club} {{ background: {club_data.get('avatar_bg', color)}; }}
""")

    club_styles_css = ''.join(club_styles)

    # Build councilors data JSON
    councilors_json = json.dumps(councilors, ensure_ascii=False)

    # Build the HTML
    canonical_url = site_url.rstrip('/') + '/moj-radny/' if site_url else ''
    meta_description = f"Znajdź swojego radnego w {city_genitive}. Sprawdź frekwencję, głosowania i aktywność radnych."
    title = f"Mój radny — {city_name} | Radoskop"

    # Prepare JSON data
    clubs_json = json.dumps(clubs, ensure_ascii=False)

    canonical_meta = f'<link rel="canonical" href="{canonical_url}">' if canonical_url else ''
    og_url_meta = f'<meta property="og:url" content="{canonical_url}">' if canonical_url else ''

    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<meta name="keywords" content="{city_name}, rada miasta, radni, frekwencja, głosowania, monitoring">
<meta name="author" content="Patryk Orwat">
{canonical_meta}
<meta property="og:type" content="website">
<meta property="og:title" content="Mój radny — {city_name}">
<meta property="og:description" content="{meta_description}">
{og_url_meta}
<meta property="og:locale" content="pl_PL">
<meta property="og:site_name" content="Radoskop {city_name}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Mój radny — {city_name}">
<meta name="twitter:description" content="{meta_description}">
<style>
:root {{
  --bg: #f8f9fa;
  --surface: #ffffff;
  --border: #e2e5e9;
  --text: #1a1d27;
  --muted: #6b7280;
  --accent: #4f46e5;
  --green: #16a34a;
  --red: #dc2626;
  --yellow: #ca8a04;
  --blue: #2563eb;
}}

html.dark {{
  --bg: #1a1d27;
  --surface: #252836;
  --border: #3a3f4f;
  --text: #f3f4f6;
  --muted: #9ca3af;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background:var(--bg);
  color:var(--text);
  line-height:1.5;
  transition: background-color 0.2s, color 0.2s;
}}

.container {{ max-width:1200px; margin:0 auto; padding:20px; }}

header {{
  padding:40px 0 20px;
  border-bottom:1px solid var(--border);
  margin-bottom:30px;
  display:flex;
  justify-content:space-between;
  align-items:flex-end;
  flex-wrap:wrap;
  gap:16px;
}}

header h1 {{
  font-size:2rem;
  font-weight:700;
  cursor:pointer;
}}

header h1 span {{ color:var(--accent); }}

header p {{ color:var(--muted); margin-top:4px; }}

.header-right {{
  display:flex;
  align-items:center;
  gap:16px;
}}

.theme-toggle {{
  background:none;
  border:1px solid var(--border);
  border-radius:8px;
  padding:8px 12px;
  cursor:pointer;
  color:var(--text);
  font-size:1rem;
  display:flex;
  align-items:center;
  justify-content:center;
}}

.theme-toggle:hover {{
  border-color:var(--accent);
  color:var(--accent);
}}

.search-bar {{
  display:flex;
  gap:8px;
  margin-bottom:24px;
  flex-wrap:wrap;
}}

.search-input {{
  flex:1;
  min-width:200px;
  padding:12px 16px;
  border:1px solid var(--border);
  border-radius:8px;
  background:var(--surface);
  color:var(--text);
  font-size:0.95rem;
}}

.search-input::placeholder {{
  color:var(--muted);
}}

.search-input:focus {{
  outline:none;
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(79,70,229,0.1);
}}

.filter-group {{
  display:flex;
  gap:8px;
  align-items:center;
  flex-wrap:wrap;
}}

.filter-label {{
  color:var(--muted);
  font-size:0.85rem;
  font-weight:500;
}}

.filter-select {{
  padding:8px 12px;
  border:1px solid var(--border);
  border-radius:8px;
  background:var(--surface);
  color:var(--text);
  cursor:pointer;
  font-size:0.9rem;
}}

.filter-select:focus {{
  outline:none;
  border-color:var(--accent);
}}

.councilors-container {{
  min-height:400px;
}}

.councilors-grid {{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(320px, 1fr));
  gap:16px;
}}

.councilor-card {{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:12px;
  padding:16px;
  transition:all 0.2s;
  cursor:pointer;
}}

.councilor-card:hover {{
  border-color:var(--accent);
  box-shadow:0 4px 12px rgba(79,70,229,0.1);
  transform:translateY(-2px);
}}

.councilor-card.hidden {{
  display:none;
}}

.card-header {{
  display:flex;
  gap:12px;
  margin-bottom:12px;
  align-items:flex-start;
}}

.councilor-avatar {{
  width:48px;
  height:48px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:700;
  color:white;
  font-size:1.2rem;
  flex-shrink:0;
}}

.card-info {{
  flex:1;
  min-width:0;
}}

.councilor-name {{
  font-weight:700;
  font-size:1rem;
  margin-bottom:2px;
  word-break:break-word;
}}

.councilor-club {{
  display:inline-block;
  padding:4px 8px;
  border-radius:4px;
  font-size:0.75rem;
  font-weight:600;
  margin-bottom:8px;
}}

.card-metrics {{
  display:grid;
  grid-template-columns:1fr 1fr 1fr;
  gap:8px;
  margin-bottom:12px;
  font-size:0.8rem;
}}

.metric {{
  background:var(--bg);
  padding:8px;
  border-radius:6px;
  text-align:center;
}}

.metric-value {{
  font-weight:700;
  font-size:1.1rem;
  color:var(--accent);
}}

.metric-label {{
  color:var(--muted);
  font-size:0.7rem;
  margin-top:2px;
  text-transform:uppercase;
}}

.rebellions {{
  border-top:1px solid var(--border);
  padding-top:12px;
}}

.rebellions-title {{
  font-size:0.75rem;
  color:var(--muted);
  text-transform:uppercase;
  margin-bottom:6px;
  font-weight:600;
}}

.rebellion {{
  padding:6px 0;
  border-bottom:1px solid var(--border);
  font-size:0.75rem;
}}

.rebellion:last-child {{
  border-bottom:none;
}}

.rebellion-date {{
  color:var(--muted);
  font-size:0.7rem;
}}

.rebellion-topic {{
  color:var(--text);
  margin:2px 0;
  line-height:1.3;
  word-break:break-word;
}}

.rebellion-vote {{
  display:inline-block;
  padding:2px 6px;
  border-radius:3px;
  font-size:0.7rem;
  font-weight:600;
  margin-top:2px;
}}

.rebellion-vote.za {{
  background:rgba(34,197,94,0.15);
  color:var(--green);
}}

.rebellion-vote.przeciw {{
  background:rgba(239,68,68,0.15);
  color:var(--red);
}}

.rebellion-vote.wstrzymal {{
  background:rgba(234,179,8,0.15);
  color:var(--yellow);
}}

.card-footer {{
  margin-top:12px;
  padding-top:12px;
  border-top:1px solid var(--border);
}}

.card-link {{
  display:inline-block;
  color:var(--accent);
  text-decoration:none;
  font-size:0.85rem;
  font-weight:500;
}}

.card-link:hover {{
  text-decoration:underline;
}}

.empty-state {{
  text-align:center;
  padding:60px 20px;
  color:var(--muted);
}}

.empty-state-icon {{
  font-size:3rem;
  margin-bottom:16px;
}}

.empty-state-title {{
  font-size:1.2rem;
  font-weight:600;
  margin-bottom:8px;
  color:var(--text);
}}

footer {{
  text-align:center;
  padding:40px 0;
  color:var(--muted);
  font-size:0.8rem;
  border-top:1px solid var(--border);
  margin-top:40px;
}}

footer a {{
  color:var(--accent);
  text-decoration:none;
}}

footer a:hover {{
  text-decoration:underline;
}}

/* Club styles */
{club_styles_css}

@media (max-width: 768px) {{
  header {{
    flex-direction:column;
    align-items:flex-start;
  }}

  header h1 {{
    font-size:1.5rem;
  }}

  .header-right {{
    width:100%;
    flex-direction:row-reverse;
  }}

  .search-bar {{
    flex-direction:column;
  }}

  .search-input {{
    min-width:auto;
  }}

  .councilors-grid {{
    grid-template-columns:1fr;
  }}

  .card-metrics {{
    grid-template-columns:1fr;
    gap:6px;
  }}
}}

@media (max-width: 480px) {{
  .container {{
    padding:12px;
  }}

  header {{
    padding:20px 0 16px;
  }}

  header h1 {{
    font-size:1.3rem;
  }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1><span>Radoskop</span> {city_name}</h1>
      <p>Mój radny</p>
    </div>
    <div class="header-right">
      <button class="theme-toggle" id="themeToggle" title="Przełącz motyw">🌙</button>
    </div>
  </header>

  <div class="search-bar">
    <input
      type="text"
      class="search-input"
      id="searchInput"
      placeholder="Wpisz nazwisko radnego lub nazwę klubu..."
      autocomplete="off"
    >
    <div class="filter-group">
      <label class="filter-label" for="clubFilter">Klub:</label>
      <select class="filter-select" id="clubFilter">
        <option value="">Wszystkie kluby</option>
      </select>
    </div>
  </div>

  <h2 style="font-size:1.5rem; font-weight:600; margin-bottom:24px;">Znajdź swoich radnych</h2>

  <div class="councilors-container">
    <div class="councilors-grid" id="councilorsGrid">
      <!-- Generated by JavaScript -->
    </div>
    <div class="empty-state" id="emptyState" style="display:none;">
      <div class="empty-state-icon">🔍</div>
      <div class="empty-state-title">Brak wyników</div>
      <p>Spróbuj zmienić kryteria wyszukiwania</p>
    </div>
  </div>
</div>

<footer>
  <p><a href="/">← Wróć do Radoskopu</a> | Otwarte dane Rady Miasta {city_genitive}</p>
</footer>

<script>
const councilorsData = PLACEHOLDER_COUNCILORS_JSON;
const clubsConfig = PLACEHOLDER_CLUBS_JSON;
const cityName = "{city_name}";

// Get unique clubs
const uniqueClubs = [...new Set(councilorsData.map(c => c.club).filter(Boolean))].sort();

// Initialize UI
function initializeUI() {{
  const clubFilter = document.getElementById('clubFilter');
  uniqueClubs.forEach(club => {{
    const option = document.createElement('option');
    option.value = club;
    option.textContent = club;
    clubFilter.appendChild(option);
  }});

  renderCouncilors();
}}

// Render all councilors
function renderCouncilors(searchTerm = '', selectedClub = '') {{
  const grid = document.getElementById('councilorsGrid');
  const emptyState = document.getElementById('emptyState');
  grid.innerHTML = '';

  const searchLower = searchTerm.toLowerCase().trim();
  let filtered = councilorsData;

  // Filter by search term
  if (searchLower) {{
    filtered = filtered.filter(c =>
      c.name.toLowerCase().includes(searchLower) ||
      c.club.toLowerCase().includes(searchLower) ||
      c.club_full.toLowerCase().includes(searchLower)
    );
  }}

  // Filter by club
  if (selectedClub) {{
    filtered = filtered.filter(c => c.club === selectedClub);
  }}

  if (filtered.length === 0) {{
    emptyState.style.display = 'block';
    return;
  }}

  emptyState.style.display = 'none';

  filtered.forEach(councilor => {{
    const card = createCouncilorCard(councilor);
    grid.appendChild(card);
  }});
}}

// Create a councilor card
function createCouncilorCard(councilor) {{
  const card = document.createElement('div');
  card.className = 'councilor-card';

  const initials = councilor.name
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  const clubClass = clubsConfig[councilor.club] ? ` avatar-${{councilor.club}}` : '';

  let rebellionsHTML = '';
  if (councilor.rebellions && councilor.rebellions.length > 0) {{
    rebellionsHTML = `
      <div class="rebellions">
        <div class="rebellions-title">Głosowania niezgodne z klubem</div>
        ${{councilor.rebellions.map(r => `
          <div class="rebellion">
            <div class="rebellion-date">${{r.session}}</div>
            <div class="rebellion-topic">${{r.topic}}</div>
            <span class="rebellion-vote ${{r.their_vote}}">${{translateVote(r.their_vote)}}</span>
          </div>
        `).join('')}}
      </div>
    `;
  }}

  card.innerHTML = `
    <div class="card-header">
      <div class="councilor-avatar${{clubClass}}">${{initials}}</div>
      <div class="card-info">
        <div class="councilor-name">${{escapeHtml(councilor.name)}}</div>
        <div class="councilor-club club club-${{councilor.club}}">${{councilor.club}}</div>
      </div>
    </div>

    <div class="card-metrics">
      <div class="metric">
        <div class="metric-value">${{councilor.frekwencja.toFixed(1)}}%</div>
        <div class="metric-label">Frekwencja</div>
      </div>
      <div class="metric">
        <div class="metric-value">${{councilor.aktywnosc.toFixed(1)}}%</div>
        <div class="metric-label">Aktywność</div>
      </div>
      <div class="metric">
        <div class="metric-value">${{councilor.zgodnosc_z_klubem.toFixed(1)}}%</div>
        <div class="metric-label">Zgodność</div>
      </div>
    </div>

    ${{rebellionsHTML}}

    <div class="card-footer">
      <a href="/${{councilor.slug}}/" class="card-link">Pełny profil →</a>
    </div>
  `;

  return card;
}}

function translateVote(vote) {{
  const map = {{
    'za': 'Za',
    'przeciw': 'Przeciw',
    'wstrzymal': 'Wstrzymał się',
    'wstrzymal_sie': 'Wstrzymał się'
  }};
  return map[vote] || vote;
}}

function escapeHtml(text) {{
  const map = {{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }};
  return text.replace(/[&<>"']/g, m => map[m]);
}}

// Search and filter handlers
const searchInput = document.getElementById('searchInput');
const clubFilter = document.getElementById('clubFilter');

searchInput.addEventListener('input', () => {{
  renderCouncilors(searchInput.value, clubFilter.value);
}});

clubFilter.addEventListener('change', () => {{
  renderCouncilors(searchInput.value, clubFilter.value);
}});

// Theme toggle
const themeToggle = document.getElementById('themeToggle');
const htmlElement = document.documentElement;

function initTheme() {{
  const savedTheme = localStorage.getItem('theme') || 'light';
  if (savedTheme === 'dark') {{
    htmlElement.classList.add('dark');
    themeToggle.textContent = '☀️';
  }} else {{
    htmlElement.classList.remove('dark');
    themeToggle.textContent = '🌙';
  }}
}}

themeToggle.addEventListener('click', () => {{
  if (htmlElement.classList.contains('dark')) {{
    htmlElement.classList.remove('dark');
    localStorage.setItem('theme', 'light');
    themeToggle.textContent = '🌙';
  }} else {{
    htmlElement.classList.add('dark');
    localStorage.setItem('theme', 'dark');
    themeToggle.textContent = '☀️';
  }}
}});

// Initialize on load
initTheme();
initializeUI();
</script>
</body>
</html>
"""

    return html.replace('PLACEHOLDER_COUNCILORS_JSON', councilors_json).replace('PLACEHOLDER_CLUBS_JSON', clubs_json)


def main():
    parser = argparse.ArgumentParser(description='Generate Mój radny pages for cities')
    parser.add_argument('--base', required=True, help='Path to gdansk-network directory')
    parser.add_argument('--city', help='Generate for single city (e.g., radoskop-gdansk)')

    args = parser.parse_args()

    base_path = Path(args.base)

    # Find all city directories
    if args.city:
        city_dirs = [base_path / args.city]
    else:
        city_dirs = sorted([d for d in base_path.iterdir() if d.is_dir() and d.name.startswith('radoskop-')])

    for city_dir in city_dirs:
        if not city_dir.exists():
            print(f"City directory not found: {city_dir}")
            continue

        config_path = city_dir / 'config.json'
        profiles_path = city_dir / 'docs' / 'profiles.json'

        if not config_path.exists():
            print(f"config.json not found in {city_dir}")
            continue

        if not profiles_path.exists():
            print(f"profiles.json not found in {city_dir}")
            continue

        print(f"Generating for {city_dir.name}...")

        # Load data
        with open(config_path) as f:
            config = json.load(f)

        with open(profiles_path) as f:
            profiles_data = json.load(f)

        # Generate HTML
        html = generate_html(config, profiles_data, city_dir)

        if html:
            # Create output directory
            output_dir = city_dir / 'docs' / 'moj-radny'
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / 'index.html'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)

            print(f"✓ Generated {output_path}")
        else:
            print(f"✗ Failed to generate for {city_dir.name}")


if __name__ == '__main__':
    main()
