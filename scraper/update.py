"""The scheduled job: fetch every source, keep last good data, build site/data.json.

Run with:  python -m scraper.update
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import build, eu_bulletin, hr_mzoe, napoved, si_gov
from .models import Forecast, Period

TZ = ZoneInfo("Europe/Ljubljana")
USER_AGENT = "cene-goriva-bot/1.0"
EU_HOUR_UTC = 5
ALERT_AFTER = timedelta(hours=3)  # email the owner only when a source has been failing this long
ALERT_EVERY = timedelta(hours=24)  # ...and then at most once a day


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


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _alerts(status_file: Path, attempted: list[str], failed: set[str], now: datetime) -> list[str]:
    """Sources the owner should be emailed about: failing for 3+ hours, at most once a day each.

    status.json only changes when a source starts/stops failing or an alert is sent,
    so it adds no commits while everything works.
    """
    status = _read(status_file) or {}
    for name in attempted:
        if name in failed:
            status.setdefault(name, {"failing_since": _iso(now)})
        else:
            status.pop(name, None)
    alerts = []
    for name, entry in sorted(status.items()):
        since = datetime.fromisoformat(entry["failing_since"])
        alerted = entry.get("alerted_at")
        if now - since >= ALERT_AFTER and (alerted is None or now - datetime.fromisoformat(alerted) >= ALERT_EVERY):
            entry["alerted_at"] = _iso(now)
            alerts.append(name)
    if status or status_file.exists():
        _write(status_file, status)
    return alerts


def run(now: datetime, fetch: Callable[[str], bytes], data_dir: Path, out_file: Path) -> dict:
    today = today_in_ljubljana(now)
    utc = now.astimezone(timezone.utc)
    caches = {name: data_dir / f"{name}.json" for name in ("si_gov", "hr_mzoe", "eu_bulletin", "napoved")}
    errors: list[dict] = []
    attempted: list[str] = []

    def attempt(name: str, job: Callable[[], None]) -> None:
        attempted.append(name)
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
    attempt("napoved", do_napoved)
    # The EU file is large and weekly: once a day (the job runs hourly), or when we have nothing yet.
    if utc.hour == EU_HOUR_UTC or not caches["eu_bulletin"].exists():
        attempt("eu_bulletin", do_eu)

    official = _periods(_read(caches["si_gov"])) + _periods(_read(caches["hr_mzoe"]))
    periods = build.combine(official, _periods(_read(caches["eu_bulletin"])))
    forecasts = [Forecast.from_json(d) for d in (_read(caches["napoved"]) or {}).get("forecasts", [])]
    forecasts += build.hr_estimates(periods, forecasts, today)
    data = build.site_data(periods, forecasts, errors, now, today)
    data["alerts"] = _alerts(data_dir / "status.json", attempted, {e["source"] for e in errors}, now)

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
