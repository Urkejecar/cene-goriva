# Cene goriv — Slovenia & Croatia fuel price website

Date: 2026-11-17
Status: draft, awaiting approval

## Intent

A small website the user, their family and a few friends open on their phones to see
**today's petrol (95) and diesel prices in Slovenia and Croatia**, the **expected next
price** as soon as it is known, and a **chart of how prices moved** over the last week,
month, year or five years.

Why: prices change every Tuesday in both countries. In Slovenia the expected new price is
known from Thursday/Saturday (forecast) and the official one on Monday afternoon. The user
wants to see these **as soon as the news comes out**, without searching news sites.

It must be **free** to run and reachable on the internet by anyone with the link.

## Goals

- Current regulated price of Bencin/Eurosuper 95 and diesel for SI and HR, with change vs
  previous week and the date range it is valid for.
- Slovenia: expected price for next Tuesday (from napovedgoriv.si), shown clearly as
  "pričakovano" (expected), with source credit and link.
- New data appears on the site within ~30 minutes of being published at the source.
- Chart with range buttons: 1 week, 1 month, 1 year, 5 years.
- Country toggle: Slovenia, Croatia, or both — each country its own colour.
- Fuel toggle: petrol 95, diesel (one at a time keeps the chart readable; see "Calls").
- Opens fast on a phone (tiny static page + small JSON, no server work on page load).
- Can be added to the phone home screen (web app manifest + icon).
- Shows "last updated" time so stale data is never mistaken for fresh data.

## Non-goals

- Prices at individual stations, motorway (unregulated) prices, cheapest-station finder.
- Croatian forecast (no reliable structured source exists; news guesses only).
- Push notifications, user accounts, LPG / heating oil / blue diesel.
- Native Android/iOS app.

## Anti-goals (failure even if it "works")

- Costs money to keep running.
- Shows an old price as if it were current (must always show validity dates + last update).
- An expected price that could be mistaken for the official one.
- Silently stops updating with no visible sign.

## Constraints

- Free hosting, no paid server. User is non-technical; setup steps must be guided.
- The user currently has no GitHub CLI installed; a free GitHub account is needed.
- Sources have no official APIs except plain file downloads; parsers must tolerate small
  format changes and fail loudly (keep last good data, record the error).

## Approaches considered

1. **Static site on GitHub Pages + scheduled GitHub Actions job (chosen).** A Python script
   runs on a schedule, fetches the sources, writes small JSON files, commits them; Pages
   serves the site. Free for public repos, no server, fast page loads. Delay: Actions
   cron can run a few–15 min late; fine for "within ~30 min".
2. Cloudflare Pages + Workers cron. Also free and slightly more punctual, but more setup
   (two services, KV storage) for no real gain here.
3. Native mobile app. Store fees/sideloading for every family member; rejected.

The user handed over the "how" ("I just want it on the internet for free"), so approach 1
is Claude's call.

## Data sources

| What | Source | Format | Notes |
|---|---|---|---|
| SI official weekly, since 2022-06-21 | `https://www.gov.si/teme/cene-naftnih-derivatov/element/162094/izvoz.csv` | CSV, UTF-8 BOM, `"od 17. 11. do 23. 11. 2026","1.444","1.798"` | Newest first. Published Monday afternoon, valid Tue–Mon. Older rows are 14-day periods. |
| SI forecast | `https://napovedgoriv.si/` | HTML page | First forecast Thu morning, final Sat. No API; fetch at most hourly, credit + link on site. |
| HR official weekly | Narodne novine: latest "Uredba o utvrđivanju najviših maloprodajnih cijena naftnih derivata" (`narodne-novine.nn.hr`) | HTML | Published Monday, valid from Tuesday for the period stated in the decree (currently 7 days, earlier 14). Parse Eurosuper 95 and Eurodizel max prices and the validity dates. |
| History both countries (before official tables / HR backfill) | EU Weekly Oil Bulletin history xlsx: `https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx` | XLSX, sheet "Prices with taxes", €/1000 l | Weekly national averages since 2005. Used for 5-year chart before official series start. |
| (Optional fallback, HR) | `https://webservis.mzoe-gor.hr/api/trend-cijena` | JSON `[{dat_poc, avg_cijena, tip_goriva_id}]` | Daily average of all stations, ~2 months only. Not the regulated price; use only if NN parsing breaks. |

Series rule: for each country & fuel, use the official regulated series where it exists,
EU bulletin values before that. The chart marks this (tooltip says source).

## Design

**Repository layout (proposal)**

```
site/            index.html, app.js, style.css, manifest.json, icons, vendored Chart.js
site/data/       prices.json (history), latest.json (current + forecast + updated_at, errors)
scraper/         Python: one module per source + build step that merges into JSON
tests/           parser tests against saved sample files of each source
.github/workflows/update.yml   scheduled scrape + commit
.github/workflows/pages.yml    deploy site/ to GitHub Pages
```

**Update job**: runs every 30 min (GitHub cron, UTC). Fetches SI official, SI forecast,
HR official every run; EU history once a day. Writes JSON only if content changed, so
commits happen only on real changes (a few per week). Each source is independent: if one
fails, its previous data is kept and the error + time is recorded in `latest.json`.
Note: GitHub disables scheduled workflows after 60 days without repo activity; the
weekly data commits keep it alive.

**Deploy and "last checked"**: the update job deploys `site/` to Pages on *every* run
(using the Pages deploy action, not by committing), stamping `checked_at` into
`latest.json`. Data history (`prices.json`) is committed to the repo only when it changes.
So the page always shows when sources were last checked ("preverjeno 17.11. 14:05"),
and a dead job is visible: if `checked_at` is older than 3 hours, the page shows a
yellow "podatki morda niso sveži" (data may be stale) banner. One workflow does both
update and deploy.

**Three price states per country**, decided by date, not by "newest row":
1. *Velja* (in effect today): the period containing today.
2. *Uradno od torka* (official, published, not yet in effect): a period starting after
   today, e.g. Monday evening. Shown in its own clearly labelled line on the card; it
   replaces the forecast line.
3. *Pričakovano* (SI forecast only): shown only while no official upcoming price exists,
   labelled "first"/"final" per napovedgoriv.si and with its source.
The chart's dashed extension shows state 2 if present, otherwise state 3.

**Period lengths are read from the source**, never assumed: Croatian decrees have run 14
days at times and 7 days lately; older SI rows are 14-day periods. "Change" is vs. the
previous period, whatever its length.

**When a source breaks**: the update job keeps the last good data for that source and
records the error in `latest.json`. Sanity checks reject parsed prices outside
0.80–3.50 €/l or with a period that doesn't fit the existing timeline, so a half-broken
parse can't publish wrong numbers. Family members see only the friendly stale banner
(no error text). The maintainer (the user) gets GitHub's default "workflow failed" email
and comes back to Claude to fix the parser. No automatic switch to the mzoe station-average
fallback (it's a different kind of price and would mislead).

**Data shape** (each price stored as a period, so step charts are exact):
`{country: "SI"|"HR", fuel: "petrol95"|"diesel", from: "2026-11-17", to: "2026-11-23", price: 1.444, source: "gov.si"|"nn.hr"|"eu-bulletin"}`
Forecast: `{country:"SI", fuel, from: next Tuesday, price, status: "first"|"final", source_updated}`.

**Page**:

```
 ⛽ Cene goriv                         posodobljeno: 17.11. 14:05
 ┌──── Slovenija ─────────────┐ ┌──── Hrvaška ──────────────┐
 │ Bencin 95  1,444 €  ▼6,2 c │ │ Eurosuper 95 1,56 €  ▼5 c │
 │ Dizel      1,798 €  ▼5,0 c │ │ Eurodizel    1,82 €  ▼3 c │
 │ velja 17.–23. 11.          │ │ velja 17.–23. 11.          │
 │ Pričakovano od 24. 11.:    │ │                            │
 │  bencin 1,41 · dizel 1,77  │ │                            │
 │  (napovedgoriv.si)         │ │                            │
 └────────────────────────────┘ └────────────────────────────┘
 [Bencin 95 | Dizel]   [SI ✓] [HR ✓]
 [1 teden] [1 mesec] [1 leto] [5 let]
  step chart: SI blue, HR red; SI forecast = dashed extension to next week
```

- Step-line chart (prices are constant within a period). Range = last 7/31/365/1826 days
  ending today (plus forecast week when present). Tooltip: date range, price, source.
- Country toggles are checkboxes; at least one stays on.
- Remember last chosen fuel/range/countries in localStorage (per device convenience).
- Plain HTML/CSS/JS + Chart.js (vendored file, no build step). Works in light/dark mode.

## Calls Claude made (user can override)

- UI language: Slovenian (family/friends are presumed Slovenian speakers).
- One fuel at a time on the chart with a toggle (4 lines at once gets cluttered).
- Expected prices only for Slovenia, sourced from napovedgoriv.si with credit; polite
  hourly-at-most fetching. Recommend the user emails the site owner as a courtesy.
- Regulated (off-motorway) prices only.
- Public GitHub repository (required for free Pages + free Actions minutes); the data is
  public anyway and contains nothing personal.
- Monday evening: cards show today's price as "velja" plus a separate "Uradno od torka"
  line with the new official price (it replaces the forecast).
- Maintenance: the user gets GitHub's failure email and asks Claude to fix; family sees
  only a "data may be stale" banner. No silent fallback to station averages.
- "Preverjeno" time = last time sources were checked (deploy every run), so a stopped
  job is visible.

## Left to the builder

- Exact HTML parsing of napovedgoriv.si and Narodne novine (save samples for tests).
- How to locate the latest NN decree (search page / listing) and backfill HR official
  decrees as far back as practical.
- EU bulletin column names for SI/HR in "Prices with taxes".
- Icon, colours (accessible in light/dark), exact cron expression.
- Step-by-step setup guide for the user (create GitHub account, create repo, push,
  enable Pages) — the user is non-technical.
