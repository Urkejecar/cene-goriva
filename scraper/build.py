"""Merge the sources into the single data file the page reads."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from .models import Forecast, Period

HISTORY_DAYS = 1830  # a bit more than 5 years
HR_VAT = 0.25


def combine(official: list[Period], eu: list[Period]) -> list[Period]:
    """Official periods, plus EU averages only for dates before each official series starts."""
    first_official: dict[tuple[str, str], date] = {}
    for p in official:
        key = (p.country, p.fuel)
        if key not in first_official or p.start < first_official[key]:
            first_official[key] = p.start

    result = list(official)
    before: dict[tuple[str, str], list[Period]] = {}
    for p in eu:
        key = (p.country, p.fuel)
        cutoff = first_official.get(key)
        if cutoff is None:
            result.append(p)
        elif p.start < cutoff:
            before.setdefault(key, []).append(p)
    for key, eu_periods in before.items():
        eu_periods.sort(key=lambda p: p.start)
        last_day = first_official[key] - timedelta(days=1)
        result += [replace(p, end=min(p.end, last_day)) for p in eu_periods[:-1]]
        # The last EU week runs up to the official data, so the line steps instead of slanting.
        result.append(replace(eu_periods[-1], end=last_day))
    result.sort(key=lambda p: (p.country, p.fuel, p.start))
    return result


def hr_estimates(periods: list[Period], si_forecasts: list[Forecast], today: date) -> list[Forecast]:
    """Expected HR prices for next week: today's HR price moved by the market change behind the SI forecast.

    Both countries set prices weekly from the same oil quotes (Platts, Mediterranean),
    so the market change per litre is the same; only VAT differs. Excise and margin
    changes by the Croatian government are not known in advance.
    """
    result = []
    for fc in si_forecasts:
        if fc.country != "SI" or fc.market is None:
            continue
        hr = [p for p in periods if p.country == "HR" and p.fuel == fc.fuel and p.source == "mzoe" and p.start <= today]
        if not hr:
            continue
        current = max(hr, key=lambda p: p.start)
        if current.start >= fc.start:
            continue
        price = round(current.price + fc.market * (1 + HR_VAT) + 1e-9, 2)
        result.append(Forecast("HR", fc.fuel, fc.start, price, "estimate", fc.updated, fc.known, fc.days, fc.market))
    return result


def site_data(
    periods: list[Period], forecasts: list[Forecast], errors: list[dict], checked_at: datetime, today: date
) -> dict:
    oldest = today - timedelta(days=HISTORY_DAYS)
    return {
        "checked_at": checked_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today.isoformat(),
        "periods": [
            p.to_json() for p in sorted(periods, key=lambda p: (p.country, p.fuel, p.start)) if p.end >= oldest
        ],
        "forecasts": [f.to_json() for f in forecasts if f.start > today],
        "errors": errors,
    }
