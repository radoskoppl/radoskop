# Radoskop

Open data dashboard for Polish city councils. We scrape session protocols and
roll-call votes from each council's BIP (Biuletyn Informacji Publicznej),
build per-councillor metrics (attendance, club loyalty, rebellion, similarity)
and publish them as static sites + JSON API.

Live: [radoskop.pl](https://radoskop.pl)

## Where the data lives

**Not in this repo.** All scrape outputs (per-city `docs/*.json`, per-councillor
profiles, OG images, generated HTML) live in the public S3 bucket
**`radoskop-public`** (`eu-central-1`). Monorepo holds only code, configs,
templates and the apex page source.

Three public read endpoints, all backed by the same bucket:

| URL | Purpose |
|---|---|
| `https://{slug}.radoskop.pl/` | Per-city website. Cloudflare Worker routes `{slug}.radoskop.pl/*` to `s3://radoskop-public/{slug}/*`. |
| `https://data.radoskop.pl/{slug}/...` | Same bucket, explicit CORS. Use this from notebooks, R, scripts. |
| `https://radoskop-public.s3.eu-central-1.amazonaws.com/{slug}/...` | Direct S3 (no CDN). Best for batch downloads, parallel ranges. |

Apex page (`radoskop.pl`) lives at the `_main/` prefix:
`s3://radoskop-public/_main/{cities.json,index.html,...}`.

Schema docs and pull patterns: see
[`radoskop-premium/DATA_BUCKET.md`](https://github.com/radoskoppl/radoskop-premium/blob/main/DATA_BUCKET.md).

## Currently monitored

24 cities (top 14 by population scraped, 10 newer ones with metadata + BIP
links awaiting per-city scrapers): Warszawa, Kraków, Łódź, Wrocław, Poznań,
Gdańsk, Szczecin, Bydgoszcz, Lublin, Białystok, Katowice, Gdynia, Sopot,
Częstochowa, Radom, Toruń, Rzeszów, Kielce, Olsztyn, Bielsko-Biała, Gliwice,
Zabrze, Bytom, Tychy.

Adding a new city: add a row to `data/cities-meta.csv`, drop a `config.json`
into `cities/{slug}/`, and either subclass `EsesjaScraper` (eSesja platform)
or `BipScraper` (custom BIP) with a 30-line wrapper in
`cities/{slug}/scripts/scrape_{slug}.py`. See `scripts/lib_esesja.py` and
`scripts/lib_bip_static.py` for the contract.

## Repo layout

```
radoskop/
├── data/cities-meta.csv             single source of truth: slug,voivodeship,population
├── docs/                            apex page (deployed to s3://.../_main/)
│   ├── index.html                   data-driven main page (24+ cities)
│   └── (cities.json, sitemap.xml)   regenerated each run, gitignored
├── cities/{slug}/
│   ├── config.json                  per city: site_url, BIP, clubs, kadencje
│   ├── scripts/scrape_{slug}.py     thin wrapper around lib_esesja / lib_bip_static
│   └── docs/                        scrape outputs — gitignored, deployed to S3
├── scripts/
│   ├── lib_esesja.py                generic eSesja scraper (one class, many cities)
│   ├── lib_bip_static.py            abstract base for custom BIP scrapers
│   ├── generate_site.py             render docs/index.html from template + data.json
│   ├── generate_seo_pages.py        per-radny / per-vote SEO pages
│   ├── generate_og_images.py        OG cards for social previews
│   ├── generate_feed.py             RSS/Atom + /aktualnosci/ page
│   ├── parse_pdf.py                 PDF → JSON for Gdańsk pipeline
│   └── build_metrics.py             roll-up sessions/votes → data.json
└── template/index.html              per city template, populated by generate_site
```

What's gitignored (lives on S3 instead of git):
- `cities/*/docs/` — per-city scrape output (data.json, kadencja-*.json,
  profiles.json, generated HTML, OG images, sitemaps)
- `cities/*/.cache/`, `cities/*/data/`, `cities/*/pdfs/` — scrape scratch
- `docs/{cities,controversial-votes,votes-index,councilors-index}.json`,
  `docs/sitemap*.xml` — apex manifests, regenerated every run

## What it measures

- **Frekwencja** — % of votes the councillor was registered as voting (any side)
- **Aktywność** — % of votes where the councillor took a position (vs. abstain/absent)
- **Zgodność z klubem** — % of votes matching the majority of the councillor's club
- **Bunty** — votes where the councillor went against their club majority
- **Macierz podobieństwa** — pairwise voting similarity across the council

## Running locally

You don't need to clone the data; pull what you need from S3:

```bash
# Manifest of all cities
curl -s https://data.radoskop.pl/_main/cities.json | jq '.[] | .slug'

# Full kadencja for one city
curl -s https://data.radoskop.pl/gdansk/kadencja-2024-2029.json > gdansk.json

# Cross-city aggregates
curl -s https://data.radoskop.pl/_main/votes-index.json > votes.json
```

To regenerate a single city's site files from a fresh scrape locally:

```bash
pip install requests beautifulsoup4 lxml playwright pdfplumber
python cities/bytom/scripts/scrape_bytom.py \
  --output cities/bytom/docs/data.json \
  --profiles cities/bytom/docs/profiles.json
```

The full pipeline (scrape → reports → deploy) lives in
[`radoskop-premium/nas/`](https://github.com/radoskoppl/radoskop-premium/tree/main/nas)
and runs on a Synology NAS (Polish residential IP avoids BIP geo-blocks).

## Architecture at a glance

```
        ┌──────────────────────┐
        │  Synology NAS        │
        │  (scrape + build)    │
        └──┬───────────────────┘
           │ pushes JSON + HTML
           ▼
        ┌──────────────────────┐
        │  s3://radoskop-public│  source of truth for data
        │  (eu-central-1)      │
        └──┬───────────────────┘
           │
     ┌─────┼─────────────────────────────┐
     ▼     ▼                             ▼
 Cloudflare Worker            api.radoskop.pl
 *.radoskop.pl                (Lightsail Flask cache over S3)
     │                             │
     ▼                             ▼
  static city sites           JSON API for the per city UIs
```

## Data sources

Session protocols and roll-call votes published in BIP by each city council.
Roll-call voting (głosowanie imienne) is mandatory for Polish municipal
councils since 2018. CMS varies: most cities use eSesja (`{city}.esesja.pl`),
larger cities run custom BIPs (Liferay for Warszawa, ASP.NET for Łódź,
Bydgoszcz/Wrocław PDF protocols, etc.).

## Use of generative AI

This project uses generative AI tools (Claude, GitHub Copilot) during
development for code generation, data analysis and documentation. All
AI-generated outputs are reviewed and validated by the maintainer.

## Related projects

- [Open Raadsinformatie](https://github.com/openstate/open-raadsinformatie) —
  Open State Foundation's tool for Dutch municipal councils. Similar mission.

## License

Code: AGPL-3.0. Data: CC-BY 4.0 (source remains BIP, reuse with attribution).
