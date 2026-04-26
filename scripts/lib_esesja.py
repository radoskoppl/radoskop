#!/usr/bin/env python3
"""
Generic eSesja scraper library for Radoskop.

eSesja (esesja.pl) is a common BIP CMS used by many Polish municipalities for
publishing session minutes and roll-call votes. URL conventions are stable
across cities, so one parameterised scraper covers any city on the platform.

Usage from a per-city wrapper:

    from lib_esesja import EsesjaScraper

    KADENCJE = {
        "2024-2029": {"label": "IX kadencja (2024–2029)", "start": "2024-05-07"},
    }
    COUNCILORS = {
        # Optional: name -> club mapping. eSesja uses "Lastname Firstname".
        # Without this, club fields are empty but everything else still works.
    }

    EsesjaScraper(
        base_url="https://bytom.esesja.pl",
        kadencje=KADENCJE,
        councilors=COUNCILORS,
    ).run_cli()  # parses --output/--profiles/--max-sessions/--dry-run/--delay

Source url conventions:
  /glosowania             — paginated session list
  /listaglosowan/{UUID}   — votes in one session
  /glosowanie/{ID}/{HASH} — one vote with named results

Vote page structure:
  <div class='wim'><h3>ZA<span class='za'> (30)</span></h3>
    <div class='osobaa'>Surname FirstName</div>
    ...
  </div>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Zainstaluj: pip install beautifulsoup4 lxml", file=sys.stderr)
    raise

try:
    import requests
except ImportError:
    print("Zainstaluj: pip install requests", file=sys.stderr)
    raise


# ---------------------------------------------------------------------------
# Stateless helpers
# ---------------------------------------------------------------------------

MONTHS_PL = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
    "luty": 2, "marzec": 3, "kwiecień": 4, "maj": 5,
    "czerwiec": 6, "lipiec": 7, "sierpień": 8, "wrzesień": 9,
    "październik": 10, "listopad": 11, "grudzień": 12, "styczeń": 1,
}


def parse_polish_date(text: str) -> str | None:
    """Parse '25 Listopada 2024 r.' or '25 Listopada 2024' → '2024-11-25'."""
    text = text.strip().rstrip(".")
    text = re.sub(r"\s*r\.?$", "", text)
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))
    month = MONTHS_PL.get(month_name)
    if not month:
        return None
    return f"{year}-{month:02d}-{day:02d}"


def make_slug(name: str) -> str:
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
        "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
    }
    slug = name.lower()
    for pl, asc in replacements.items():
        slug = slug.replace(pl, asc)
    return slug.replace(" ", "-").replace("'", "")


def build_name_lookup(councilors: dict[str, str]) -> dict[str, str]:
    """Map name (multiple formats) → club. Handles Firstname/Lastname swap."""
    lookup: dict[str, str] = {}
    for name, club in councilors.items():
        lookup[name] = club
        parts = name.split()
        if len(parts) >= 2:
            lookup[f"{parts[-1]} {' '.join(parts[:-1])}"] = club
            lookup[f"{parts[-1]} {parts[0]}"] = club
    return lookup


def compact_named_votes(output: dict) -> dict:
    """Index councilor names per kadencja so vote lists can use ints, not full names."""
    for kad in output.get("kadencje", []):
        names: set[str] = set()
        for v in kad.get("votes", []):
            for cat_names in v.get("named_votes", {}).values():
                for n in cat_names:
                    if isinstance(n, str):
                        names.add(n)
        if not names:
            continue
        index = sorted(names, key=lambda n: n.split()[-1] + " " + n)
        name_to_idx = {n: i for i, n in enumerate(index)}
        kad["councilor_index"] = index
        for v in kad.get("votes", []):
            nv = v.get("named_votes", {})
            for cat in nv:
                nv[cat] = sorted(
                    name_to_idx[n]
                    for n in nv[cat]
                    if isinstance(n, str) and n in name_to_idx
                )
    return output


def save_split_output(output: dict, out_path: Path) -> None:
    """Save data.json (slim index) + kadencja-{id}.json files alongside it."""
    compact_named_votes(output)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stubs = []
    for kad in output.get("kadencje", []):
        kid = kad["id"]
        stubs.append({"id": kid, "label": kad.get("label", f"Kadencja {kid}")})
        kad_path = out_path.parent / f"kadencja-{kid}.json"
        with kad_path.open("w", encoding="utf-8") as f:
            json.dump(kad, f, ensure_ascii=False, separators=(",", ":"))
    index = {
        "generated": output.get("generated", ""),
        "default_kadencja": output.get("default_kadencja", ""),
        "kadencje": stubs,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))


def load_profiles(profiles_path: str | Path) -> dict:
    path = Path(profiles_path)
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return {p["name"]: p for p in data.get("profiles", [])}
    except Exception:
        return {}


def _write_empty_outputs(
    output_path: str | Path,
    profiles_path: str | Path,
    kadencje: dict,
    default_kadencja: str,
) -> None:
    """Write a valid-but-empty trio of files when scrape produced no data.

    Generators downstream (generate_reports.py, generate_main_manifest.py)
    expect specific JSON shapes — missing files cause hard FileNotFoundError
    failures. Emitting empty-but-valid versions lets the pipeline continue.
    """
    out = Path(output_path)
    prof = Path(profiles_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prof.parent.mkdir(parents=True, exist_ok=True)

    kid = default_kadencja
    label = kadencje[kid].get("label", f"Kadencja {kid}")

    # data.json: index pointing at the kadencja stub
    index = {
        "generated": datetime.now().isoformat(),
        "default_kadencja": kid,
        "kadencje": [{"id": kid, "label": label}],
        "_status": "no_data",
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    # kadencja-{id}.json: empty but well-formed
    kad_stub = {
        "id": kid,
        "label": label,
        "clubs": {},
        "sessions": [],
        "total_sessions": 0,
        "total_votes": 0,
        "total_councilors": 0,
        "councilors": [],
        "votes": [],
        "similarity_top": [],
        "similarity_bottom": [],
    }
    with (out.parent / f"kadencja-{kid}.json").open("w", encoding="utf-8") as f:
        json.dump(kad_stub, f, ensure_ascii=False, separators=(",", ":"))

    # profiles.json: shape `{"profiles": []}` (load_city_data expects dict)
    with prof.open("w", encoding="utf-8") as f:
        json.dump({"profiles": []}, f, ensure_ascii=False, indent=2)


def build_profiles_json(output: dict, profiles_path: str | Path) -> None:
    profiles = []
    for kad in output["kadencje"]:
        kid = kad["id"]
        for c in kad["councilors"]:
            entry = {
                "club": c.get("club", "?"),
                "frekwencja": c.get("frekwencja", 0),
                "aktywnosc": c.get("aktywnosc", 0),
                "zgodnosc_z_klubem": c.get("zgodnosc_z_klubem", 0),
                "votes_za": c.get("votes_za", 0),
                "votes_przeciw": c.get("votes_przeciw", 0),
                "votes_wstrzymal": c.get("votes_wstrzymal", 0),
                "votes_brak": c.get("votes_brak", 0),
                "votes_nieobecny": c.get("votes_nieobecny", 0),
                "votes_total": c.get("votes_total", 0),
                "rebellion_count": c.get("rebellion_count", 0),
                "rebellions": c.get("rebellions", []),
                "has_voting_data": True,
                "has_activity_data": c.get("has_activity_data", False),
                "roles": [],
                "notes": "",
                "former": False,
                "mid_term": False,
            }
            if c.get("activity"):
                entry["activity"] = c["activity"]
            profiles.append({
                "name": c["name"],
                "slug": make_slug(c["name"]),
                "kadencje": {kid: entry},
            })
    path = Path(profiles_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"profiles": profiles}, f, ensure_ascii=False, indent=2)
    print(f"  Zapisano profiles.json: {len(profiles)} profili")


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class EsesjaScraper:
    """Stateful scraper for one eSesja-hosted council.

    Every state previously held in scrape_bialystok module globals lives on
    the instance, so multiple scrapers can run in the same process if needed.
    """

    UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        base_url: str,
        kadencje: dict,
        councilors: dict | None = None,
        delay: float = 1.0,
        default_kadencja: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.sessions_url = f"{self.base_url}/glosowania"
        self.kadencje = kadencje
        self.councilors = councilors or {}
        self.club_lookup = build_name_lookup(self.councilors)
        self.delay = delay
        # Default kadencja: the only one that's currently active (no end date).
        # Falls back to the first key in `kadencje`.
        if default_kadencja:
            self.default_kadencja = default_kadencja
        else:
            self.default_kadencja = next(iter(self.kadencje.keys()))
        self._session: requests.Session | None = None

    # -- HTTP layer --------------------------------------------------------

    def _init_session(self) -> None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.UA,
            "Accept-Language": "pl-PL,pl;q=0.9",
        })
        self._session = s

    def fetch(self, url: str) -> BeautifulSoup:
        if self._session is None:
            self._init_session()
        time.sleep(self.delay)
        print(f"  GET {url}")
        resp = self._session.get(url, timeout=30)  # type: ignore[union-attr]
        resp.raise_for_status()
        # eSesja declares windows-1250 in meta but not HTTP header; requests
        # otherwise falls back to ISO-8859-1 and mangles Polish characters.
        if "esesja" in url:
            resp.encoding = "windows-1250"
        return BeautifulSoup(resp.text, "lxml")

    # -- Club resolution ---------------------------------------------------

    def resolve_club(self, name: str) -> str:
        if name in self.club_lookup:
            return self.club_lookup[name]
        parts = name.split()
        if parts:
            last = parts[0]
            for key, club in self.club_lookup.items():
                if key.split()[0] == last or key.split()[-1] == last:
                    return club
        return ""

    # -- Step 1: session list ----------------------------------------------

    def scrape_session_list(self) -> list[dict]:
        sessions: list[dict] = []
        page = 1
        while True:
            url = self.sessions_url if page == 1 else f"{self.sessions_url}/{page}"
            try:
                soup = self.fetch(url)
            except Exception as e:
                print(f"  Nie udalo sie pobrac {url}: {e}")
                break

            found_on_page = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/listaglosowan/" not in href:
                    continue
                text = a.get_text(strip=True)
                m = re.search(r"w\s+dniu\s+(\d{1,2})\s+(\w+)\s+(\d{4})", text)
                if not m:
                    continue
                day = int(m.group(1))
                month = MONTHS_PL.get(m.group(2).lower())
                year = int(m.group(3))
                if not month:
                    continue
                date_str = f"{year}-{month:02d}-{day:02d}"
                full_url = href if href.startswith("http") else self.base_url + href
                nr_match = re.search(r"nr\s+([IVXLCDM]+)", text)
                session_number = nr_match.group(1) if nr_match else ""
                sessions.append({
                    "id": full_url.split("/")[-1],
                    "date": date_str,
                    "number": session_number,
                    "url": full_url,
                    "title": text,
                })
                found_on_page += 1

            if found_on_page == 0:
                break
            next_link = soup.find("a", href=re.compile(rf"/glosowania/{page + 1}\b"))
            if not next_link:
                break
            page += 1

        if not sessions:
            print("  UWAGA: Nie znaleziono sesji!")
            return []

        seen: set[str] = set()
        unique = []
        for s in sessions:
            if s["url"] not in seen:
                seen.add(s["url"])
                unique.append(s)

        kadencja_start = self.kadencje[self.default_kadencja]["start"]
        filtered = [s for s in unique if s["date"] >= kadencja_start]
        print(
            f"  Znaleziono {len(unique)} sesji ogolnie, "
            f"{len(filtered)} w kadencji {self.default_kadencja}"
        )
        return sorted(filtered, key=lambda x: x["date"])

    # -- Step 2: votes per session -----------------------------------------

    def scrape_votes_from_session(self, session: dict) -> list[dict]:
        votes: list[dict] = []
        try:
            soup = self.fetch(session["url"])
        except Exception as e:
            print(f"    Blad pobierania sesji: {e}")
            return votes

        seen_urls: set[str] = set()
        vote_links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/glosowanie/" not in href or "/listaglosowan/" in href:
                continue
            url = href if href.startswith("http") else self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)
            vote_links.append(url)

        print(f"    Znaleziono {len(vote_links)} linkow do glosowan")

        for idx, url in enumerate(vote_links):
            vote = self._scrape_single_vote(url, session, idx)
            if vote:
                votes.append(vote)
            time.sleep(self.delay * 0.5)

        print(f"    Wyodrebniono {len(votes)} glosowan z imiennymi wynikami")
        return votes

    def _scrape_single_vote(self, url: str, session: dict, vote_idx: int) -> dict | None:
        try:
            soup = self.fetch(url)
        except Exception as e:
            print(f"      Blad pobierania {url}: {e}")
            return None

        h1 = soup.find("h1")
        topic = h1.get_text(strip=True)[:500] if h1 else ""
        topic = re.sub(r"^Wyniki głosowania jawnego w sprawie:\s*", "", topic).strip()
        topic = re.sub(r"^Wyniki głosowania w sprawie:?\s*", "", topic).strip()
        topic = re.sub(r"^Głosowanie\s+w\s+sprawie\s+", "", topic).strip()
        if not topic:
            topic = f"Glosowanie {vote_idx + 1}"

        named_votes: dict[str, list[str]] = {
            "za": [], "przeciw": [], "wstrzymal_sie": [], "brak_glosu": [], "nieobecni": [],
        }
        category_map = {
            "za": "za",
            "przeciw": "przeciw",
            "wstrzymuj": "wstrzymal_sie",
            "brak g": "brak_glosu",
            "nieobecn": "nieobecni",
        }
        for wim in soup.find_all("div", class_="wim"):
            h3 = wim.find("h3")
            if not h3:
                continue
            h3_text = h3.get_text(strip=True).upper()
            cat_key = None
            for prefix, key in category_map.items():
                if h3_text.upper().startswith(prefix.upper()):
                    cat_key = key
                    break
            if not cat_key:
                continue
            for osoba in wim.find_all("div", class_="osobaa"):
                name = osoba.get_text(strip=True)
                if name and len(name) > 2:
                    named_votes[cat_key].append(name)

        if sum(len(v) for v in named_votes.values()) == 0:
            return None

        counts = {cat: len(named_votes[cat]) for cat in named_votes}
        return {
            "id": f"{session['date']}_{vote_idx:03d}_000",
            "source_url": url,
            "session_date": session["date"],
            "session_number": session.get("number", ""),
            "topic": topic[:500],
            "druk": None,
            "resolution": None,
            "counts": counts,
            "named_votes": named_votes,
        }

    # -- Step 3: aggregations ---------------------------------------------

    def build_councilors(
        self,
        all_votes: list[dict],
        sessions: list[dict],
        existing_profiles: dict,
    ) -> list[dict]:
        stats: dict[str, dict] = defaultdict(lambda: {
            "name": "", "club": "", "district": None,
            "votes_za": 0, "votes_przeciw": 0, "votes_wstrzymal": 0,
            "votes_brak": 0, "votes_nieobecny": 0, "votes_total": 0,
            "frekwencja": 0, "aktywnosc": 0, "zgodnosc_z_klubem": 0,
            "rebellion_count": 0, "rebellions": [],
            "has_voting_data": True, "has_activity_data": False,
        })

        for vote in all_votes:
            for cat, names in vote["named_votes"].items():
                for name in names:
                    stats[name]["name"] = name
                    stats[name]["club"] = self.resolve_club(name)
                    stats[name]["votes_total"] += 1
                    if cat == "za":
                        stats[name]["votes_za"] += 1
                    elif cat == "przeciw":
                        stats[name]["votes_przeciw"] += 1
                    elif cat == "wstrzymal_sie":
                        stats[name]["votes_wstrzymal"] += 1
                    elif cat == "brak_glosu":
                        stats[name]["votes_brak"] += 1

        for _, s in stats.items():
            if s["votes_total"] > 0:
                s["frekwencja"] = round(
                    (s["votes_total"] - s["votes_brak"]) / s["votes_total"] * 100, 1
                )
                s["aktywnosc"] = round(
                    (s["votes_za"] + s["votes_przeciw"] + s["votes_wstrzymal"])
                    / s["votes_total"] * 100, 1
                )

        result = []
        for name, s in sorted(stats.items()):
            if name in existing_profiles:
                s.update({k: v for k, v in existing_profiles[name].items() if k not in s or not s[k]})
            result.append(s)
        return result

    @staticmethod
    def compute_similarity(all_votes: list[dict], councilors: list[dict]) -> tuple[list, list]:
        name_to_club = {c["name"]: c.get("club", "?") for c in councilors}
        vectors: dict[str, dict] = defaultdict(dict)
        for v in all_votes:
            for cat in ["za", "przeciw", "wstrzymal_sie"]:
                for name in v["named_votes"].get(cat, []):
                    vectors[name][v["id"]] = cat

        names = sorted(vectors.keys())
        pairs = []
        for a, b in combinations(names, 2):
            common = set(vectors[a].keys()) & set(vectors[b].keys())
            if len(common) < 10:
                continue
            same = sum(1 for vid in common if vectors[a][vid] == vectors[b][vid])
            score = round(same / len(common) * 100, 1)
            pairs.append({
                "a": a, "b": b,
                "club_a": name_to_club.get(a, "?"),
                "club_b": name_to_club.get(b, "?"),
                "score": score,
                "common_votes": len(common),
            })
        pairs.sort(key=lambda x: x["score"], reverse=True)
        return pairs[:20], pairs[-20:][::-1]

    @staticmethod
    def build_sessions(sessions_raw: list[dict], all_votes: list[dict]) -> list[dict]:
        votes_by_date: dict[str, list[dict]] = defaultdict(list)
        for v in all_votes:
            votes_by_date[v["session_date"]].append(v)
        result = []
        for s in sessions_raw:
            date = s["date"]
            session_votes = votes_by_date.get(date, [])
            attendees: set[str] = set()
            for v in session_votes:
                for cat in ["za", "przeciw", "wstrzymal_sie", "brak_glosu"]:
                    attendees.update(v["named_votes"].get(cat, []))
            # eSesja's session listing typically doesn't expose a stable number.
            # Without a fallback the per-city template generates /sesja// links.
            # Use date as the URL slug — every session has one.
            number = s.get("number", "") or date
            result.append({
                "date": date,
                "number": number,
                "vote_count": len(session_votes),
                "attendee_count": len(attendees),
                "attendees": sorted(attendees),
                "speakers": [],
            })
        return sorted(result, key=lambda x: x["date"])

    # -- Top-level run -----------------------------------------------------

    def run(
        self,
        output_path: str | Path,
        profiles_path: str | Path,
        max_sessions: int = 0,
        dry_run: bool = False,
    ) -> int:
        self._init_session()
        slug = self.base_url.split("//", 1)[-1].split(".", 1)[0]
        print(f"\n=== Radoskop {slug} — eSesja scraper ===\n")

        print("[1/4] Pobieranie listy sesji...")
        sessions = self.scrape_session_list()
        if not sessions:
            print("UWAGA: Nie znaleziono sesji — zapisuję pusty wynik.")
            _write_empty_outputs(output_path, profiles_path, self.kadencje, self.default_kadencja)
            return 0
        if max_sessions > 0:
            sessions = sessions[:max_sessions]
        print(f"  Znaleziono {len(sessions)} sesji\n")

        if dry_run:
            print("Dry-run: Zatrzymuję się tutaj.")
            return 0

        print("[2/4] Pobieranie głosowań z sesji...")
        all_votes: list[dict] = []
        for i, session in enumerate(sessions):
            print(f"  [{i+1}/{len(sessions)}] Sesja {session['id']} ({session['date']})")
            all_votes.extend(self.scrape_votes_from_session(session))
        print(f"  Pobrano {len(all_votes)} głosowań\n")

        print("[3/4] Budowanie danych...")
        existing_profiles = load_profiles(profiles_path)
        councilors = self.build_councilors(all_votes, sessions, existing_profiles)
        sessions_data = self.build_sessions(sessions, all_votes)
        sim_top, sim_bottom = self.compute_similarity(all_votes, councilors)

        club_counts: dict[str, int] = defaultdict(int)
        for c in councilors:
            club_counts[c["club"]] += 1

        print(f"  {len(sessions_data)} sesji, {len(all_votes)} głosowań, {len(councilors)} radnych")
        print(f"  Kluby: {dict(club_counts)}\n")

        kid = self.default_kadencja
        kad_output = {
            "id": kid,
            "label": self.kadencje[kid]["label"],
            "clubs": {club: count for club, count in sorted(club_counts.items())},
            "sessions": sessions_data,
            "total_sessions": len(sessions_data),
            "total_votes": len(all_votes),
            "total_councilors": len(councilors),
            "councilors": councilors,
            "votes": all_votes,
            "similarity_top": sim_top,
            "similarity_bottom": sim_bottom,
        }
        output = {
            "generated": datetime.now().isoformat(),
            "default_kadencja": kid,
            "kadencje": [kad_output],
        }

        print("[4/4] Zapisywanie danych...")
        out_path = Path(output_path)
        save_split_output(output, out_path)
        print(f"Gotowe! Zapisano do {out_path}")
        print(f"  {len(sessions_data)} sesji, {len(all_votes)} głosowań, {len(councilors)} radnych\n")

        build_profiles_json(output, profiles_path)
        return 0

    def run_cli(self, prog_name: str | None = None) -> int:
        """Wrap run() with the standard --output/--profiles/--max-sessions CLI."""
        parser = argparse.ArgumentParser(description=prog_name or "eSesja scraper")
        parser.add_argument("--output", default="docs/data.json")
        parser.add_argument("--profiles", default="docs/profiles.json")
        parser.add_argument("--max-sessions", type=int, default=0)
        parser.add_argument("--delay", type=float, default=1.0)
        parser.add_argument("--dry-run", action="store_true")
        # `--cache-dir` accepted but ignored, kept for compatibility with
        # scrape_all.sh's per-city CLI conventions.
        parser.add_argument("--cache-dir", default=None)
        args = parser.parse_args()
        if args.delay != 1.0:
            self.delay = args.delay
        return self.run(
            output_path=args.output,
            profiles_path=args.profiles,
            max_sessions=args.max_sessions,
            dry_run=args.dry_run,
        )


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def make_scraper(
    base_url: str,
    kadencje: dict,
    councilors: dict | None = None,
    delay: float = 1.0,
) -> EsesjaScraper:
    return EsesjaScraper(base_url, kadencje, councilors, delay=delay)
