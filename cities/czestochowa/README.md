# Radoskop Częstochowa

Monitoring głosowań Rady Miasta Częstochowy.

- Dashboard: https://czestochowa.radoskop.pl
- BIP: https://bip.czestochowa.pl
- Repo: https://github.com/radoskoppl/radoskop-czestochowa

## Struktura

- `docs/` statyczna strona publikowana przez GitHub Pages na czestochowa.radoskop.pl
- `scripts/scrape_czestochowa.py` scraper protokołów z BIP
- `scripts/scrape.sh` wrapper uruchamiający scraper w venv
- `config.json` konfiguracja miasta używana przez generate_site.py

## Uruchomienie

```bash
bash scripts/scrape.sh
```

## Regeneracja strony

```bash
python3 ../radoskop/scripts/generate_site.py --config config.json --output docs/
```
