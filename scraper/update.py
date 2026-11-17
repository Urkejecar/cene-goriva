"""The scheduled job: fetch every source, keep last good data, build site/data.json.

Run with:  python -m scraper.update
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import build, eu_bulletin, hr_mzoe, napoved, si_gov
from .models import Forecast, Period

TZ = ZoneInfo("Europe/Ljubljana")
USER_AGENT = "cene-goriva-bot/1.0"
EU_HOUR_UTC = 5  # refresh the (large, weekly) EU file once a day


def today_in_ljubljana(now: datetime) -> date:
    return now.astimezone(TZ).date()


def http_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _read(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, content: dict) -> None:
    """Write JSON only if it changed, so unchanged data creates no commit."""
    text = json.dumps(content, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _periods(cache: dict | None) -> list[Period]:
    return [Period.from_json(d) for d in (cache or {}).get("periods", [])]


def run(now: datetime, fetch: Callable[[str], bytes], data_dir: Path, out_file: Path) -> dict:
    today = today_in_ljubljana(now)
    utc = now.astimezone(timezone.utc)
    caches = {name: data_dir / f"{name}.json" for name in ("si_gov", "hr_mzoe", "eu_bulletin", "napoved")}
    errors: list[dict] = []

    def attempt(name: str, job: Callable[[], None]) -> None:
        try:
            job()
        except Exception as e:  # each source fails on its own; keep its last good cache
            errors.append({"source": name, "message": f"{type(e).__name__}: {e}"})

    def do_si() -> None:
        periods = si_gov.parse(fetch(si_gov.URL).decode("utf-8"))
        _write(caches["si_gov"], {"periods": [p.to_json() for p in periods]})

    def do_hr() -> None:
        prices = hr_mzoe.regulated_prices(fetch(hr_mzoe.URL))
        existing = _periods(_read(caches["hr_mzoe"]))
        updated: list[Period] = []
        for fuel, price in sorted(prices.items()):
            series = sorted((p for p in existing if p.fuel == fuel), key=lambda p: p.start)
            updated += hr_mzoe.record_observation(series, fuel, today, price)
        _write(caches["hr_mzoe"], {"periods": [p.to_json() for p in updated]})

    def do_napoved() -> None:
        forecasts = napoved.parse(fetch(napoved.URL).decode("utf-8"))
        _write(caches["napoved"], {"forecasts": [f.to_json() for f in forecasts]})

    def do_eu() -> None:
        periods = eu_bulletin.parse(fetch(eu_bulletin.URL))
        _write(caches["eu_bulletin"], {"periods": [p.to_json() for p in periods]})

    attempt("si_gov", do_si)
    attempt("hr_mzoe", do_hr)
    # napovedgoriv.si: at most once an hour (the :00 run), or when we have nothing yet.
    if utc.minute < 30 or not caches["napoved"].exists():
        attempt("napoved", do_napoved)
    if (utc.hour == EU_HOUR_UTC and utc.minute < 30) or not caches["eu_bulletin"].exists():
        attempt("eu_bulletin", do_eu)

    official = _periods(_read(caches["si_gov"])) + _periods(_read(caches["hr_mzoe"]))
    periods = build.combine(official, _periods(_read(caches["eu_bulletin"])))
    forecasts = [Forecast.from_json(d) for d in (_read(caches["napoved"]) or {}).get("forecasts", [])]
    data = build.site_data(periods, forecasts, errors, now, today)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def main() -> int:
    data = run(datetime.now(timezone.utc), http_fetch, Path("data"), Path("site/data.json"))
    print(f"{len(data['periods'])} periods, {len(data['forecasts'])} forecasts, {len(data['errors'])} errors")
    for e in data["errors"]:
        print(f"  {e['source']}: {e['message']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
