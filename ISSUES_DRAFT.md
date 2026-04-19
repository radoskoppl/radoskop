# 10 draftów issues do github.com/radoskoppl/radoskop/issues

Gotowe do wklejenia. Każdy issue ma tytuł, labelki, opis, kryteria akceptacji, szacowany effort. Sekcje rozdzielone "==="..

===

## Issue 1

**Title:** Regression tests for eSesja PDF parser (golden file suite)

**Labels:** `area/parser`, `priority/high`, `type/quality`

**Motivation**

The eSesja PDF format is our single parsing target across 13 cities. A silent change to the format (new column, renamed header, different date format) would break ingestion for every city at once. Today we have no automated guardrails against this. The risk is realized every time eSesja ships an update.

**Scope**

Add a golden file test suite that covers representative PDFs from each of the 13 currently supported cities, plus edge cases (split sessions, attendance checks only, missing councillors).

**Acceptance criteria**

1. `tests/fixtures/` contains at least 20 PDFs (2 per supported city, 2 edge cases) with committed expected output JSON.
2. `pytest` runs the parser on each fixture, diffs against expected output, and fails on any mismatch.
3. CI (GitHub Actions) runs the suite on every push and pull request.
4. README documents how to add a new fixture when onboarding a city.

**Effort:** 1 to 2 days.

===

## Issue 2

**Title:** Incremental scraping with session ID skip (avoid full rebuild per run)

**Labels:** `area/pipeline`, `priority/high`, `type/performance`

**Motivation**

Current daily pipeline re-scrapes all historical sessions for every city on every run. For Katowice this takes ~113 minutes (673 votes × ~10s per PDF with pdfplumber). Warszawa takes ~55 minutes. When we scale from 13 to 230 samorządów, linear re-scraping becomes the dominant cost.

A parsed-vote cache was added for Katowice in a recent PR. This issue generalizes that pattern to all cities and adds a session-level skip (if session_id seen, PDFs parsed, outputs current, skip the entire session page fetch).

**Scope**

1. Parsed-vote cache by stable vote URL, as already implemented for Katowice.
2. Session manifest: per city, JSON listing session_id + last processed timestamp + list of vote URLs. On run, fetch only sessions missing from manifest or marked dirty.
3. Cache invalidation via `PARSED_CACHE_VERSION` bump when parser semantics change.

**Acceptance criteria**

1. All 13 city scrapers accept `--parsed-dir` and `--manifest` flags.
2. Warm-cache full-pipeline run completes in under 20 minutes total (vs current ~113 minutes).
3. First cold run after version bump rebuilds correctly and writes manifest.
4. Logs print cache hit/miss counts at the end of each city run.

**Effort:** 3 to 5 days.

===

## Issue 3

**Title:** RODO / cookie compliance footer and information clause

**Labels:** `area/compliance`, `priority/high`, `type/legal`

**Motivation**

Radoskop has no RODO footer, no cookie banner, and no information clause on any city dashboard. Councillor data is public under UDIP (ustawa o dostępie do informacji publicznej), so the legal basis for processing exists, but an information clause is best practice and a requirement for B2B sales (media, think tanks, law firms all check this during procurement).

**Scope**

1. Static footer on every dashboard page listing: administrator of data (Patryk Orwat JDG or legal entity once established), source of data (BIP + UDIP basis), user rights, contact.
2. Cookie consent banner if Google Analytics or Plausible is added.
3. `/polityka-prywatnosci` and `/regulamin` pages generated for every city.

**Acceptance criteria**

1. Every dashboard page renders the footer with correct administrator and contact info.
2. Cookie banner present on pages that load third-party scripts.
3. Privacy policy and terms pages are indexable and linked from footer.
4. No RODO-sensitive PII is collected from visitors (zero forms without explicit consent).

**Effort:** 1 day.

===

## Issue 4

**Title:** Email alert subscriptions (per city, per councillor, per topic)

**Labels:** `area/product`, `priority/medium`, `type/feature`

**Motivation**

Journalists and NGOs watching specific councillors or policy areas have to manually revisit dashboards. An email alert triggered on new vote matching filter criteria is a clear value-add, and the natural entry point for the Hobbyist tier (19 PLN/m) in the monetization plan.

**Scope**

1. Signup form with email + optional Stripe or Gumroad payment for paid tier.
2. Filter types: councillor, club, city, keyword in topic.
3. Delivery: daily digest at 08:00 CET or weekly on Mondays. Configurable per subscription.
4. Unsubscribe link in every email (CAN-SPAM basic hygiene).

**Acceptance criteria**

1. User can sign up, confirm email (double opt-in), and configure filters.
2. Matching new votes trigger email within 24 hours of daily pipeline completion.
3. Unsubscribe works end to end.
4. Free tier limited to 1 filter; paid tier unlimited.

**Effort:** 4 to 6 days.

===

## Issue 5

**Title:** SEO landing pages per councillor (long-tail organic discovery)

**Labels:** `area/seo`, `priority/medium`, `type/feature`

**Motivation**

Voters searching "radny jan kowalski gdansk" or "jak glosowal krzysztof kowalski katowice" today land on random news articles or nothing. Radoskop has the authoritative answer but no indexable page per councillor.

Estimated organic potential: 457 councillors × 50 to 200 monthly searches each = 20k to 90k long-tail impressions per month at full coverage.

**Scope**

1. Static HTML page per councillor at `/{city}/radny/{slug}/` containing: profile, latest 10 votes, frekwencja, club, photo if available, rebellions count.
2. Open Graph and Twitter Card metadata for social sharing.
3. Sitemap entry for each councillor page.
4. Schema.org Person markup.

**Acceptance criteria**

1. Every councillor in every city has an indexable static page.
2. Sitemap includes all councillor URLs with lastmod.
3. Page renders correctly on mobile (Radoskop traffic is mostly mobile).
4. Rich preview works when URL is pasted into Facebook, LinkedIn, X.

**Effort:** 2 to 3 days (builder already exists for city profiles, needs generalization).

===

## Issue 6

**Title:** Full-text vote search across all cities (Meilisearch or Whoosh)

**Labels:** `area/product`, `priority/medium`, `type/feature`

**Motivation**

"Kiedy Rada Warszawy ostatnio głosowała nad ZPI na Woli?" is a question every journalist and activist has. Currently the answer requires clicking through sessions one by one. A full-text search over vote topics and resolutions collapses that to a few seconds.

**Scope**

1. Index all vote topics, resolution titles, and druk numbers across 13 cities.
2. Search UI at `/szukaj` with filters: city, date range, club, vote outcome.
3. Result page links to vote detail view.
4. Static index build (Meilisearch self-hosted or Whoosh) in the pipeline, no runtime backend.

**Acceptance criteria**

1. Search returns results for queries in Polish with diacritic tolerance.
2. Filters compose correctly (city + date + keyword).
3. Index rebuild runs as part of daily pipeline without blocking.
4. Median search latency under 200ms.

**Effort:** 3 to 4 days.

===

## Issue 7

**Title:** Councillor comparison view (side by side, up to 4)

**Labels:** `area/product`, `priority/low`, `type/feature`

**Motivation**

"How does our councillor compare to others in the same club?" and "Which two councillors vote most alike?" are natural follow-up questions after landing on a profile. A comparison view drives engagement and makes the similarity matrix tangible.

**Scope**

1. New route `/{city}/porownaj?radni=slug1,slug2,slug3,slug4`.
2. Table with rows per metric (frekwencja, aktywność, zgodność z klubem, bunty), columns per selected councillor.
3. Vote by vote diff view (votes where selected councillors disagreed).
4. Shareable URL preserving selection.

**Acceptance criteria**

1. Up to 4 councillors can be selected and compared.
2. Diff view highlights disagreements visually.
3. URL persists selection, opens same view when shared.

**Effort:** 2 to 3 days.

===

## Issue 8

**Title:** Plausible or GA4 analytics with per-city event tracking

**Labels:** `area/observability`, `priority/medium`, `type/infrastructure`

**Motivation**

Radoskop ships no analytics. We cannot answer "how many people visit each city dashboard", "which councillor pages are most viewed", "what do visitors search for". Without this data, product prioritization is guesswork and investor conversations lack basic engagement numbers.

**Scope**

1. Add Plausible (privacy-friendly, self-hostable) OR GA4 tracking to every dashboard page.
2. Event tracking for: city page view, councillor page view, search, CSV export click, newsletter signup.
3. Public Plausible dashboard (if Plausible chosen) linked from /statystyki for transparency.

**Acceptance criteria**

1. Page views tracked across all 13 cities.
2. Events fire for at least 5 key actions.
3. RODO-compliant: if Plausible, no cookie banner needed; if GA4, cookie banner required (coordinates with Issue 3).
4. Public dashboard (Plausible case) available.

**Effort:** 1 day.

===

## Issue 9

**Title:** Auto-generated weekly newsletter per city ("Co się działo w radzie")

**Labels:** `area/product`, `priority/medium`, `type/feature`

**Motivation**

Pay-per-view raporty strategy (see monetyzacja plan, 2026-04-13 launch) depends on generating defensible weekly content. Doing this by hand for 13 cities is unsustainable. Auto-generation from vote data, with light human review before publish, is the only scalable path.

**Scope**

1. Template: "W tygodniu YYYY-MM-DD do YYYY-MM-DD Rada {city} przeprowadziła N głosowań. Najważniejsze: top 3 by vote margin, top 3 by rebellion count, top 3 by topic heuristic (budżet, plan, ulica, spółka, personalia)."
2. Output formats: HTML (for email), Markdown (for blog/Substack), PDF (for paid tier).
3. Trigger: weekly cron on Monday at 06:00.
4. Optional human-review step (generate draft, flag for maintainer approval before send).

**Acceptance criteria**

1. Script produces newsletter for any city and date range.
2. Output is copy-paste ready for Substack or Mailchimp.
3. Topic heuristic correctly categorizes at least 70% of votes.
4. Pipeline integration documented.

**Effort:** 3 to 4 days.

===

## Issue 10

**Title:** Open Graph + Twitter Card preview images per vote, per councillor, per city

**Labels:** `area/growth`, `priority/low`, `type/feature`

**Motivation**

When a journalist pastes a Radoskop link into X, LinkedIn, or Slack, the preview is currently generic Radoskop logo. A dynamic preview card with the vote topic, counts, and small party breakdown drives click-through. This is table stakes for organic virality and gets higher CTR from journalists sharing links to colleagues.

**Scope**

1. Generate OG image (1200×630 PNG) for: every city dashboard, every councillor profile, every vote detail page.
2. Templates: Headline, subtitle (counts or period), small branding, optional photo or chart.
3. Build as part of pipeline, serve as static files.
4. `<meta property="og:image">` and Twitter Card tags on every page.

**Acceptance criteria**

1. Sharing any Radoskop URL produces a rich card in Slack, X, LinkedIn, Facebook.
2. OG images regenerate when underlying data changes (vote counts, rebellion counts).
3. Branding is consistent and legible at small scale (LinkedIn feed thumbnail).

**Effort:** 2 to 3 days.

===

## Podsumowanie

| # | Issue | Priority | Effort | Obszar |
|---|-------|----------|--------|--------|
| 1 | Parser regression tests | high | 1 do 2 dni | quality |
| 2 | Incremental scraping + cache | high | 3 do 5 dni | performance |
| 3 | RODO footer + cookie | high | 1 dzień | compliance |
| 4 | Email alert subscriptions | medium | 4 do 6 dni | product/revenue |
| 5 | SEO landing per councillor | medium | 2 do 3 dni | growth |
| 6 | Full-text vote search | medium | 3 do 4 dni | product |
| 7 | Councillor comparison view | low | 2 do 3 dni | product |
| 8 | Plausible/GA4 analytics | medium | 1 dzień | observability |
| 9 | Weekly auto newsletter | medium | 3 do 4 dni | product/revenue |
| 10 | Open Graph preview images | low | 2 do 3 dni | growth |

Łączny effort: ~22 do 34 dni roboczych. Sensowna kolejność realizacji:

1. #3 (RODO, 1d) + #1 (testy, 1-2d) + #8 (analytics, 1d) = fundament, pierwsze 3-4 dni
2. #2 (incremental cache, 3-5d) = odblokowuje skalowanie na 230 samorządów
3. #5 (SEO councillor pages, 2-3d) + #10 (OG images, 2-3d) = growth, 4-6 dni
4. #4 (email alerts, 4-6d) + #9 (newsletter, 3-4d) = revenue, łączą się z pay-per-view
5. #6 (search, 3-4d) + #7 (comparison, 2-3d) = engagement, ostatnie

Każdy issue można wkleić do GitHub jako osobny z tytułem + treścią. Labelki trzeba utworzyć wcześniej (area/*, priority/*, type/*).
