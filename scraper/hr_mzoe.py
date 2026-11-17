"""Croatian regulated prices, derived from the Ministry of Economy station data.

The government decree (Narodne novine) only contains the price formula, so the
regulated maximum price is taken as the most common price across all stations.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from dataclasses import replace
from datetime import date, timedelta

from .models import Period, SourceError
from .sanity import MAX_PRICE, MIN_PRICE

URL = "https://webservis.mzoe-gor.hr/data.gz"

# vrsta_goriva ids: Eurosuper 95 with/without additives; Eurodizel with/without additives
FUEL_KINDS = {"petrol95": {1, 2}, "diesel": {7, 8}}
MIN_STATIONS = 100
MIN_SHARE = 0.40


def regulated_prices(gz: bytes) -> dict[str, float]:
    try:
        data = json.loads(gzip.decompress(gz))
        kind_of = {g["id"]: g["vrsta_goriva_id"] for g in data["gorivos"]}
        stations = data["postajas"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SourceError(f"mzoe data unreadable: {e}") from e

    counts = {fuel: Counter() for fuel in FUEL_KINDS}
    for station in stations:
        for entry in station.get("cjenici") or []:
            kind = kind_of.get(entry.get("gorivo_id"))
            for fuel, kinds in FUEL_KINDS.items():
                if kind in kinds and entry.get("cijena") is not None:
                    counts[fuel][round(float(entry["cijena"]), 3)] += 1

    result = {}
    for fuel, counter in counts.items():
        if not counter:
            raise SourceError(f"mzoe: no prices for {fuel}")
        price, n = counter.most_common(1)[0]
        total = sum(counter.values())
        if n < MIN_STATIONS or n / total < MIN_SHARE:
            raise SourceError(f"mzoe: no clear regulated price for {fuel} ({price} at {n}/{total} stations)")
        if not MIN_PRICE <= price <= MAX_PRICE:
            raise SourceError(f"mzoe: implausible price {price} for {fuel}")
        result[fuel] = price
    return result


def record_observation(periods: list[Period], fuel: str, day: date, price: float) -> list[Period]:
    """Add one day's observed price to the HR series for `fuel` (sorted list)."""
    periods = list(periods)
    if not periods:
        return [Period("HR", fuel, day, day, price, "mzoe")]
    last = periods[-1]
    if day < last.start:
        return periods
    if price == last.price:
        periods[-1] = replace(last, end=max(last.end, day))
        return periods
    if last.start == day:
        # A different price for a day already covered: correct that day.
        periods[-1] = replace(last, price=price)
        return periods
    # The old price held until the day before the new one (even if a check was missed).
    periods[-1] = replace(last, end=day - timedelta(days=1))
    periods.append(Period("HR", fuel, day, day, price, "mzoe"))
    return periods
