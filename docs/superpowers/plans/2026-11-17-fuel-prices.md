# Cene goriv Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A free static website showing current, upcoming and expected petrol 95 / diesel prices for Slovenia and Croatia with a 1w/1m/1y/5y chart, updated every 30 minutes by a scheduled job.

**Architecture:** Python scraper (`scraper/`) fetches four sources, keeps last-good per-source caches in `data/` (committed), and builds one `site/data.json`. A plain HTML/JS page (`site/`) with Chart.js renders it. One GitHub Actions workflow runs the scraper every 30 min, commits `data/` on change, and deploys `site/` to GitHub Pages every run.

**Tech Stack:** Python 3.12 (stdlib `urllib`, `csv`, `json`, `zoneinfo`; `openpyxl`, `tzdata`), pytest; vanilla ES modules + Chart.js 4.4.1 (vendored), `node --test`; GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-11-17-fuel-prices-design.md`

## Global Constraints

- Free only: public GitHub repo, GitHub Pages, GitHub Actions. No paid services, no server.
- All dates are calendar dates in `Europe/Ljubljana`. ISO `YYYY-MM-DD` in JSON.
- Prices in EUR per litre, rounded to 3 decimals. Sanity range 0.80–3.50 €/l.
- Countries `"SI"`, `"HR"`; fuels `"petrol95"`, `"diesel"`; sources `"gov.si"`, `"mzoe"`, `"eu-bulletin"`, `"napovedgoriv.si"`.
- napovedgoriv.si fetched at most once per 55 min, homepage only (`/api/` is disallowed by robots.txt). Credit + link shown on the page.
- HTTP User-Agent: `cene-goriva-bot/1.0` (no personal data).
- UI text in Slovenian. Expected price always labelled "Pričakovano"; never styled like an official price.
- Stale banner when `checked_at` older than 3 hours: "Podatki morda niso sveži".
- Family sees no error text; errors only in `data.json` and the failed-workflow email.

## Review Focus

1. Slovenian CSV rows that cross the new year without a start year (`"od 20. 12. do 3. 1. 2023"`) must start on 2022-12-20 → Task 2 test `test_year_crossing_without_start_year`.
2. A source that returns an error page / garbage must not wipe good data: last cache kept, error recorded → Task 6 test `test_failing_source_keeps_cache`.
3. Monday evening (official upcoming price published) and Tuesday 00:00–00:30 (no run yet) must show the right "velja"/"uradno od torka"/"pričakovano" states → Task 7 tests `test_states_monday_evening`, `test_forecast_hidden_when_official_upcoming`.
4. Croatian station data with junk prices (e.g. 13.5) or no clear majority price must not publish a wrong regulated price → Task 4 test `test_rejects_when_no_clear_majority`.
5. The 23:30 UTC run is already Tuesday in Ljubljana; "today" must be the Ljubljana date → Task 6 test `test_today_is_ljubljana_date`.

---

## File Structure

```
requirements.txt            openpyxl, tzdata
requirements-dev.txt        -r requirements.txt, pytest, pillow
pytest.ini                  testpaths = tests
scraper/__init__.py
scraper/models.py           Period, Forecast, SourceError
scraper/sanity.py           check_period, check_timeline
scraper/si_gov.py           Slovenian official CSV parser
scraper/napoved.py          napovedgoriv.si forecast parser
scraper/hr_mzoe.py          Croatian station data -> regulated price; record_observation
scraper/eu_bulletin.py      EU Weekly Oil Bulletin xlsx parser
scraper/build.py            combine official+EU series, build site data dict
scraper/update.py           orchestration, caches, CLI
scraper/check_errors.py     CLI: exit 1 if data.json has errors
data/                       per-source caches (committed, written by the job)
site/index.html, site/style.css, site/app.js, site/logic.js, site/logic.test.js
site/manifest.webmanifest, site/icon.svg, site/icon-180.png, site/icon-512.png
site/vendor/chart.umd.min.js
scripts/make_icons.py
tests/fixtures/si_gov.csv, napoved_no_forecast.html, hr_mzoe_data.gz   (already saved, real 17.11.2026 data)
tests/helpers.py            make_eu_xlsx()
tests/test_*.py
.github/workflows/update.yml
SETUP.md                    step-by-step for the user
```

---

### Task 1: Project setup, models and sanity checks

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`), `scraper/__init__.py`, `scraper/models.py`, `scraper/sanity.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Period(country: str, fuel: str, start: date, end: date, price: float, source: str)` frozen dataclass; `end` inclusive. `.to_json() -> dict` with keys `c, f, from, to, p, s`; `Period.from_json(d: dict) -> Period`.
  - `Forecast(country: str, fuel: str, start: date, price: float, status: str, updated: date)` frozen dataclass; status `"first"|"final"`. `.to_json()` keys `c, f, from, p, status, updated`; `Forecast.from_json`.
  - `class SourceError(Exception)`
  - `check_period(p: Period) -> None` raises `SourceError` if `not 0.80 <= p.price <= 3.50` or `p.end < p.start`.
  - `check_timeline(periods: list[Period]) -> None` raises `SourceError` if, within one (country, fuel), two periods overlap.

- [ ] **Step 1:** Create `.venv` (`python -m venv .venv`), install `requirements-dev.txt`. Expected: install succeeds.
- [ ] **Step 2: Write failing tests** in `tests/test_models.py`:
  - `test_period_json_roundtrip`: `Period("SI","petrol95",date(2026,11,17),date(2026,11,23),1.444,"gov.si").to_json() == {"c":"SI","f":"petrol95","from":"2026-11-17","to":"2026-11-23","p":1.444,"s":"gov.si"}` and `from_json` of that equals the original.
  - `test_forecast_json_roundtrip`: same idea, `{"c":"SI","f":"diesel","from":"2026-11-24","p":1.77,"status":"final","updated":"2026-11-21"}`.
  - `test_check_period_rejects_out_of_range`: prices 0.79 and 3.51 raise `SourceError`; 1.5 passes.
  - `test_check_period_rejects_reversed_dates`.
  - `test_check_timeline_rejects_overlap`: SI petrol 11-10..11-16 and 11-16..11-23 raise; 11-10..11-16 + 11-17..11-23 pass; HR period overlapping an SI one passes.
- [ ] **Step 3:** Run `.venv/Scripts/python -m pytest tests/test_models.py -q` — expect FAIL (import error).
- [ ] **Step 4:** Implement `scraper/models.py`, `scraper/sanity.py`.
- [ ] **Step 5:** Run tests — expect PASS.
- [ ] **Step 6:** Commit `chore: project setup, models and sanity checks`.

### Task 2: Slovenian official prices (gov.si CSV)

**Files:** Create `scraper/si_gov.py`; Test `tests/test_si_gov.py`

**Interfaces:**
- Consumes: `Period`, `SourceError`, `check_period`, `check_timeline`.
- Produces: `URL = "https://www.gov.si/teme/cene-naftnih-derivatov/element/162094/izvoz.csv"`; `parse(text: str) -> list[Period]` — two periods per row (petrol95 from column 2, diesel from column 3), source `"gov.si"`, sorted by start ascending; runs sanity checks.

Date rule: `od D. M. [YYYY] do D. M. YYYY`. If the start year is missing, use the end year, minus 1 when start month > end month. Strip the UTF-8 BOM. Raise `SourceError` if the header is missing or no row parses.

- [ ] **Step 1: Write failing tests** using `tests/fixtures/si_gov.csv`:
  - `test_parses_all_rows`: 266 periods.
  - `test_latest_row`: last SI petrol95 = `Period("SI","petrol95",date(2026,11,17),date(2026,11,23),1.444,"gov.si")`; last diesel price 1.798.
  - `test_earliest_row`: first petrol95 is 2022-06-21..2022-07-04 at 1.755.
  - `test_year_crossing_without_start_year`: the period with end 2023-01-03 starts 2022-12-20 (petrol 1.242).
  - `test_year_crossing_with_start_year`: period ending 2026-01-12 starts 2025-12-30.
  - `test_garbage_raises`: `parse("<html>Napaka</html>")` raises `SourceError`.
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Implement `parse` with `csv.reader` and one regex for the date cell.
- [ ] **Step 4:** Run — expect PASS.
- [ ] **Step 5:** Commit `feat: parse Slovenian official fuel prices`.

### Task 3: Slovenian forecast (napovedgoriv.si)

**Files:** Create `scraper/napoved.py`; Test `tests/test_napoved.py`

**Interfaces:**
- Produces: `URL = "https://napovedgoriv.si/"`; `parse(html: str) -> list[Forecast]`.

Approach: join all `self.__next_f.push([1,"..."])` string payloads, JSON-unescape each (`json.loads('"' + s + '"')`), find `"targetDate":"YYYY-MM-DD"`, `"asOf":"YYYY-MM-DD"` and the `"hero":[` array (decode with `json.JSONDecoder().raw_decode` from the `[`). For each hero item with `fuelType` in `{"gasoline": "petrol95", "diesel": "diesel"}` and non-null `forecastPrice`: `Forecast("SI", fuel, targetDate, round(forecastPrice,3), "final" if knownDays >= expectedDays else "first", asOf)`. Skip `elko`. Raise `SourceError` if `hero` is not found.

- [ ] **Step 1: Write failing tests** (fixture `tests/fixtures/napoved_no_forecast.html`, real page from 17.11.2026):
  - `test_no_forecast_yet`: returns `[]`.
  - `test_first_forecast`: in the fixture text replace (first occurrence each) `r'\"previousPrice\":1.506,\"forecastPrice\":null'` → `r'\"previousPrice\":1.506,\"forecastPrice\":1.412'` and `r'\"knownDays\":0'` → `r'\"knownDays\":3'`; expect `[Forecast("SI","petrol95",date(2026,11,24),1.412,"first",date(2026,11,17))]`.
  - `test_final_forecast`: same but `knownDays` 5 → status `"final"`.
  - `test_missing_hero_raises`: `parse("<html></html>")` raises `SourceError`.
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — expect PASS.
- [ ] **Step 5:** Commit `feat: parse napovedgoriv.si forecast`.

### Task 4: Croatian regulated price from ministry station data

**Files:** Create `scraper/hr_mzoe.py`; Test `tests/test_hr_mzoe.py`

**Interfaces:**
- Produces:
  - `URL = "https://webservis.mzoe-gor.hr/data.gz"`
  - `FUEL_KINDS = {"petrol95": {1, 2}, "diesel": {7, 8}}` (vrsta_goriva ids: Eurosuper 95 with/without additives; Eurodizel with/without additives)
  - `regulated_prices(gz: bytes) -> dict[str, float]` — for each fuel, the most common `cijena` over all `postajas[].cjenici` whose `gorivo_id` maps (via `gorivos[].vrsta_goriva_id`) into the fuel's kinds. Raise `SourceError` unless the most common price has ≥ 100 stations **and** ≥ 40 % of that fuel's price entries.
  - `record_observation(periods: list[Period], fuel: str, day: date, price: float) -> list[Period]` — HR periods for one fuel, sorted. If empty or price differs from the last period → append `Period("HR", fuel, day, day, price, "mzoe")`. If same price → last period's `end = max(end, day)`. If `day < last.start` → return unchanged. Returns a new list.

- [ ] **Step 1: Write failing tests** (fixture `tests/fixtures/hr_mzoe_data.gz`, real data 17.11.2026):
  - `test_regulated_prices_from_real_data`: `{"petrol95": 1.56, "diesel": 1.82}`.
  - `test_rejects_when_no_clear_majority`: build a small gz JSON in the test (5 stations, prices 1.56, 1.60, 1.70, 13.5, 1.61 for kind 1) → `SourceError`.
  - `test_record_extends_same_price`: [11-17..11-17 @1.56] + (11-18, 1.56) → [11-17..11-18 @1.56].
  - `test_record_starts_new_period_on_change`: + (11-24, 1.50) → two periods, last 11-24..11-24 @1.50.
  - `test_record_ignores_older_day`.
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Implement (stdlib `gzip`, `json`, `collections.Counter`).
- [ ] **Step 4:** Run — expect PASS.
- [ ] **Step 5:** Commit `feat: derive Croatian regulated price from ministry data`.

### Task 5: EU Weekly Oil Bulletin history

**Files:** Create `scraper/eu_bulletin.py`, `tests/helpers.py`; Test `tests/test_eu_bulletin.py`

**Interfaces:**
- Produces:
  - `URL = "https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"`
  - `COLUMNS = {("SI","petrol95"): "SI_price_with_tax_euro95", ("SI","diesel"): "SI_price_with_tax_diesel", ("HR","petrol95"): "HR_price_with_tax_euro95", ("HR","diesel"): "HR_price_with_tax_diesel"}`
  - `parse(xlsx: bytes) -> list[Period]` — sheet `"Prices with taxes"`; header names in row 1 (find column index by name, not position); data rows are those whose first cell is a `datetime`; skip empty values; `price = round(value / 1000, 3)` (EUR per 1000 l, also for HR before 2023); `start = row date`, `end = start + 6 days`; source `"eu-bulletin"`; sorted ascending. Raise `SourceError` if the sheet or any column is missing. Use `openpyxl.load_workbook(BytesIO(xlsx), read_only=True, data_only=True)`.
  - `tests/helpers.py`: `make_eu_xlsx(rows: list[tuple[datetime, float|None, float|None, float|None, float|None]]) -> bytes` — writes a workbook with sheet "Prices with taxes": row 1 = `["Consumer prices…", "CTR", "HR_price_with_tax_euro95", "HR_price_with_tax_diesel", "SI_price_with_tax_euro95", "SI_price_with_tax_diesel"]`, rows 2–3 = text sub-headers, then data rows `(date, "EU_", hr95, hrd, si95, sid)`.

- [ ] **Step 1: Write failing tests:**
  - `test_parses_weekly_rows`: rows `(2021-11-15, 1480.94, 1470.56, 1371.51, 1473.6)` and `(2026-11-09, 1748.83, 2024.63, 1634.36, 1950.29)` → 8 periods; HR petrol 2021-11-15..2021-11-21 @1.481; SI diesel 2026-11-09 @1.95.
  - `test_skips_empty_cells`: a row with HR values `None` yields only SI periods.
  - `test_missing_column_raises`.
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — expect PASS.
- [ ] **Step 5:** Commit `feat: parse EU Weekly Oil Bulletin history`.

### Task 6: Build site data and update orchestration

**Files:** Create `scraper/build.py`, `scraper/update.py`, `scraper/check_errors.py`; Test `tests/test_build.py`, `tests/test_update.py`

**Interfaces:**
- Consumes: all parsers above.
- Produces:
  - `build.combine(official: list[Period], eu: list[Period]) -> list[Period]` — per (country, fuel): all official periods, plus EU periods that start before that series' first official start, with `end` clipped to the day before it. If no official periods for a series, all its EU periods.
  - `build.site_data(periods: list[Period], forecasts: list[Forecast], errors: list[dict], checked_at: datetime, today: date) -> dict` → `{"checked_at": iso-8601 UTC, "today": "YYYY-MM-DD", "periods": [...to_json], "forecasts": [...], "errors": [{"source", "message"}]}`; keep periods with `end >= today - 1830 days`; forecasts only with `start > today`.
  - `update.today_in_ljubljana(now: datetime) -> date`
  - `update.run(now: datetime, fetch: Callable[[str], bytes], data_dir: Path, out_file: Path) -> dict` — returns the site data dict and writes it to `out_file`.
  - CLI: `python -m scraper.update` (real `urllib` fetch, timeout 30 s, User-Agent `cene-goriva-bot/1.0`, `data_dir=data`, `out_file=site/data.json`, exit 0 always). `python -m scraper.check_errors site/data.json` exits 1 and prints the errors if `errors` is non-empty.

Cache files in `data_dir` (JSON, pretty-printed, sorted keys so diffs stay small):
`si_gov.json {"periods"}`, `hr_mzoe.json {"periods"}`, `eu_bulletin.json {"fetched_at", "periods"}`, `napoved.json {"fetched_at", "forecasts"}`.
Per run: SI CSV always; HR always (then `record_observation` for each fuel with `today`); napoved only if its `fetched_at` is ≥ 55 min old; EU only if ≥ 20 h old. Each source in its own `try`: on any exception record `{"source": <cache name without .json>, "message": str(e)}` and leave its cache untouched. A failed throttled source is retried next run (don't update `fetched_at` on failure).

- [ ] **Step 1: Write failing tests** in `tests/test_build.py`:
  - `test_combine_uses_eu_only_before_official`: EU SI petrol weekly from 2022-06-13 (+ 2022-06-20) and official from 2022-06-21 → EU 2022-06-13..06-19, EU 2022-06-20..06-20, then official.
  - `test_combine_eu_only_series`.
  - `test_site_data_drops_old_and_past_forecasts`.
- [ ] **Step 2: Write failing tests** in `tests/test_update.py` with a fake `fetch` (dict URL → fixture bytes; EU via `make_eu_xlsx`) and `tmp_path`:
  - `test_full_run`: `now = 2026-11-17T06:00Z`; output has 266 gov.si periods, HR periods `HR petrol95 2026-11-17..2026-11-17 @1.56` and diesel @1.82, `errors == []`, all four cache files exist.
  - `test_failing_source_keeps_cache`: second run where the SI URL returns `b"<html>500</html>"` → `errors == [{"source": "si_gov", ...}]`, SI periods still present (from cache), `si_gov.json` unchanged.
  - `test_napoved_throttled`: two runs 20 min apart → napoved URL fetched once.
  - `test_today_is_ljubljana_date`: `today_in_ljubljana(datetime(2026,11,16,23,30,tzinfo=UTC)) == date(2026,11,17)`.
  - `test_check_errors_exit_code`: exit 1 with errors, 0 without.
- [ ] **Step 3:** Run — expect FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** Run full suite `.venv/Scripts/python -m pytest -q` — expect PASS.
- [ ] **Step 6:** Live smoke run: `.venv/Scripts/python -m scraper.update` then `python -m scraper.check_errors site/data.json`. Expected: exit 0, `site/data.json` has SI 2026-11-17 @1.444, HR @1.56/1.82, EU history back to 2021. If a live source differs from the fixtures, fix the parser and add the new sample as a fixture.
- [ ] **Step 7:** Commit (including `data/` caches) `feat: update job builds site data`.

### Task 7: Page logic (pure functions)

**Files:** Create `site/logic.js` (ES module); Test `site/logic.test.js` (`node --test site/`)

**Interfaces:**
- Consumes: the `data.json` shape from Task 6 (`periods[]` with `c,f,from,to,p,s`; `forecasts[]` with `c,f,from,p,status,updated`).
- Produces (all exported):
  - `todayLjubljana(date = new Date()) -> "YYYY-MM-DD"` (via `Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Ljubljana'})`).
  - `priceStates(data, country, fuel, today) -> {current, previous, upcoming, forecast}` — `current` = the latest period with `from <= today` (ignore `to`); `previous` = the period before it; `upcoming` = earliest period with `from > today`; `forecast` = matching forecast with `from > today`, but `null` when `upcoming` exists. Missing → `null`.
  - `rangeStart(range, today) -> "YYYY-MM-DD"`; ranges `"1w"`: 7, `"1m"`: 31, `"1y"`: 365, `"5y"`: 1826 days back.
  - `stepPoints(periods, country, fuel, from, to) -> [{x: ms, y: price, s: source, from, to}]` — for each period overlapping `[from, to]`, two points: at `max(period.from, from)` 00:00 UTC and at `min(period.to, to)` 23:59:59 UTC; sorted. (Straight lines between them draw exact steps; no Chart.js `stepped` needed.)
  - `extensionPoints(states) -> [{x, y, kind}]` — 2 points spanning the upcoming (kind `"official"`) or forecast (kind `"forecast"`) week (from..from+6); `[]` if neither.
  - `isStale(checkedAtIso, nowMs) -> boolean` — older than 3 h.
  - `formatPrice(p) -> "1,444 €"` (3 decimals SI, 2 decimals when the value has ≤ 2 decimals, e.g. `"1,56 €"`); `formatChange(cur, prev) -> "▼ 6,2 c" | "▲ 1,0 c" | "= 0,0 c"`.

- [ ] **Step 1: Write failing tests** (fixture data inline):
  - `test_states_normal_day`: today 2026-11-18 → current 11-17 @1.444, previous 11-10 @1.506, upcoming null.
  - `test_states_monday_evening`: periods incl. 11-24 @1.41, today 2026-11-23 → current 11-17, upcoming 11-24.
  - `test_forecast_hidden_when_official_upcoming`: forecast 11-24 present + upcoming → `forecast === null`; without upcoming → forecast returned.
  - `test_hr_open_period_still_current`: HR period 11-17..11-17, today 11-18 → current is it.
  - `test_range_start`: `rangeStart("1m","2026-11-17") === "2026-10-17"`.
  - `test_step_points_clipped`: period 11-10..11-16, window from 11-12 → first x = Date.UTC(2026,10,12).
  - `test_is_stale`: 2 h59 → false, 3 h01 → true.
  - `test_format`: `formatPrice(1.444) === "1,444 €"`, `formatPrice(1.56) === "1,56 €"`, `formatChange(1.444,1.506) === "▼ 6,2 c"`.
- [ ] **Step 2:** Run `node --test site/` — expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run — expect PASS.
- [ ] **Step 5:** Commit `feat: page logic for price states and chart data`.

### Task 8: The page

**Files:** Create `site/index.html`, `site/style.css`, `site/app.js`, `site/manifest.webmanifest`, `site/icon.svg`, `scripts/make_icons.py` → `site/icon-180.png`, `site/icon-512.png`; download `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js` → `site/vendor/chart.umd.min.js`.

**Interfaces:**
- Consumes: `logic.js` exports (Task 7), `data.json` (Task 6).

Before writing chart code, load the `dataviz` skill (colours, light/dark, legend, tooltip).

Requirements (from the spec's page sketch):
- Header "⛽ Cene goriv" + "preverjeno DD. MM. ob HH.MM" (from `checked_at`, Ljubljana time); yellow banner "Podatki morda niso sveži" when `isStale`.
- Two cards (Slovenija, Hrvaška), each: Bencin 95 / Eurosuper 95 and Dizel / Eurodizel with `formatPrice` + `formatChange`; "velja od D. M." (SI also "do D. M."); line "Uradno od torka D. M.: …" when `upcoming`; else for SI line "Pričakovano od D. M.: bencin …, dizel … (prva/končna napoved, vir: napovedgoriv.si)" with a link, visually muted/italic.
- Controls: fuel toggle [Bencin 95 | Dizel]; country checkboxes [SI][HR] (at least one stays on); range buttons [1 teden][1 mesec][1 leto][5 let]. Default: petrol95, both countries, 1 mesec. Remember choice in `localStorage` (wrapped in try/catch).
- Chart.js line chart, linear x-axis in ms with tick labels formatted `D. M.` (or `MMM YYYY` for 1y/5y), `pointRadius: 0`, SI blue / HR red (exact shades from the dataviz skill, distinct in light and dark), dashed segment for `extensionPoints` (official upcoming solid-dashed, forecast dotted). Tooltip: date range, price, source name.
- Small note under chart: "Pred začetkom uradnih podatkov: tedensko povprečje EU (Weekly Oil Bulletin). Za Hrvaško je to povprečje vseh črpalk."
- Footer: sources with links (gov.si, napovedgoriv.si, mzoe-gor.hr, EU Oil Bulletin).
- `fetch('data.json', {cache: 'no-cache'})`; on failure show "Podatkov ni bilo mogoče naložiti."
- `manifest.webmanifest` (name "Cene goriv", display standalone, icons 512 + svg), `<link rel="apple-touch-icon" href="icon-180.png">`, theme color.
- Mobile first: works at 360 px width, no horizontal scroll; light/dark via `prefers-color-scheme`.

- [ ] **Step 1:** Write `scripts/make_icons.py` (Pillow: fuel-drop/pump glyph on brand colour) and generate PNGs.
- [ ] **Step 2:** Vendor Chart.js 4.4.1.
- [ ] **Step 3:** Implement `index.html`, `style.css`, `app.js`.
- [ ] **Step 4:** Verify in a browser: `.venv/Scripts/python -m http.server 8000 -d site`, open `http://localhost:8000` (use the `run` skill to screenshot) at phone width and desktop, light and dark. Check: both cards show 17.11. prices, every range button and toggle redraws the chart, a fake forecast in `data.json` shows the "Pričakovano" line and dotted extension, setting `checked_at` 4 h back shows the banner. Revert fake edits.
- [ ] **Step 5:** Commit `feat: fuel price page`.

### Task 9: Scheduled workflow and setup guide

**Files:** Create `.github/workflows/update.yml`, `SETUP.md`

`update.yml`:
- `on: schedule: - cron: "*/30 * * * *"`, `workflow_dispatch`, `push: branches: [main]`.
- `permissions: contents: write, pages: write, id-token: write`; `concurrency: group: update, cancel-in-progress: false`.
- Job `update` (ubuntu-latest): `actions/checkout@v4` → `actions/setup-python@v5` (3.12, pip cache) → `pip install -r requirements.txt` → `python -m scraper.update` → commit `data/` if changed (`git config user.name "github-actions[bot]"`, `user.email "41898282+github-actions[bot]@users.noreply.github.com"`, `git add data && (git diff --cached --quiet || (git commit -m "data: update prices" && git push))`) → `actions/upload-pages-artifact@v3` with `path: site` → `actions/deploy-pages@v4` (environment `github-pages`) → final step `python -m scraper.check_errors site/data.json` (fails the run *after* deploying so the user gets GitHub's failure email).
- Add a `test` job on `push` only: install dev deps, `pytest -q`, `node --test site/`.

`SETUP.md`: plain-language steps for the user: create a free GitHub account; create a public repository `cene-goriva`; push this folder (exact commands); Settings → Pages → Source "GitHub Actions"; Actions tab → run "update" once; the site address `https://<username>.github.io/cene-goriva/`; how to add to the home screen (Android Chrome / iPhone Safari); what the failure email means ("come back to Claude").

- [ ] **Step 1:** Write `update.yml`; check it parses: `npx --yes js-yaml .github/workflows/update.yml` prints the parsed object without error. (Full validation is the first real run in Task 10.)
- [ ] **Step 2:** Write `SETUP.md`.
- [ ] **Step 3:** Run full local suite: `pytest -q` and `node --test site/` — PASS.
- [ ] **Step 4:** Commit `ci: scheduled update and Pages deploy`.

### Task 10: Go live (with the user)

Not code — done together with the user following `SETUP.md`.

- [ ] **Step 1:** User creates GitHub account and empty public repo; Claude adds the remote and pushes (`git push -u origin main`) after the user confirms.
- [ ] **Step 2:** User enables Pages (Source: GitHub Actions) and runs the workflow once.
- [ ] **Step 3:** Verify: workflow green; the site URL loads on the user's phone with today's prices; after ≥ 1 h a second scheduled run appears in the Actions tab.
