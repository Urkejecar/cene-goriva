"""Slovenian expected prices from napovedgoriv.si (unofficial forecast).

The site has no API (robots.txt disallows /api/), so we read the homepage only.
It is a Next.js app: the page data sits in `self.__next_f.push([1,"..."])`
script payloads as JS-escaped strings. The headline forecast is in the `"hero"`
array, but it stays empty until a few market days are known. The `"explain"`
object (the site's "how it's calculated" section) already has an early
forecast from the first known day, plus the market price change behind it.
"""
from __future__ import annotations

import json
import re
from datetime import date

from .models import Forecast, SourceError
from .sanity import MAX_PRICE, MIN_PRICE

URL = "https://napovedgoriv.si/"

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', re.S)
_FUELS = {"gasoline": "petrol95", "diesel": "diesel"}


def _payload(html: str) -> str:
    parts = []
    for raw in _PUSH.findall(html):
        try:
            parts.append(json.loads('"' + raw + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _date_field(blob: str, name: str, start: int) -> date:
    m = re.compile(r'"' + name + r'":"(\d{4}-\d{2}-\d{2})"').search(blob, max(0, start - 500))
    if not m:
        raise SourceError(f"napovedgoriv.si: {name} not found")
    return date.fromisoformat(m.group(1))


def _object(blob: str, key: str):
    idx = blob.find(f'"{key}":')
    if idx < 0:
        return None, -1
    value, _ = json.JSONDecoder().raw_decode(blob, idx + len(key) + 3)
    return value, idx


def parse(html: str) -> list[Forecast]:
    blob = _payload(html)
    hero, idx = _object(blob, "hero")
    if not isinstance(hero, list):
        raise SourceError("napovedgoriv.si: forecast data ('hero') not found")
    target = _date_field(blob, "targetDate", idx)
    as_of = _date_field(blob, "asOf", idx)
    explain, _ = _object(blob, "explain")
    if not isinstance(explain, dict):
        explain = {}

    forecasts = []
    for item in hero:
        fuel = _FUELS.get(item.get("fuelType"))
        if fuel is None:
            continue
        detail = explain.get(item["fuelType"]) or {}
        price = item.get("forecastPrice")
        if price is None:
            price = detail.get("forecastPrice")
        known, expected = item.get("knownDays") or 0, item.get("expectedDays") or 5
        if price is None or known == 0:
            continue
        price = round(float(price), 3)
        if not MIN_PRICE <= price <= MAX_PRICE:
            raise SourceError(f"napovedgoriv.si: implausible forecast {price}")
        market = detail.get("marketDeltaBeforeVat")
        market = round(float(market), 6) if market is not None else None
        status = "final" if known >= expected else "first"
        forecasts.append(Forecast("SI", fuel, target, price, status, as_of, known, expected, market))
    return forecasts
