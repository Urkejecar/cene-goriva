"""Slovenian expected prices from napovedgoriv.si (unofficial forecast).

The site has no API (robots.txt disallows /api/), so we read the homepage only.
It is a Next.js app: the page data sits in `self.__next_f.push([1,"..."])`
script payloads as JS-escaped strings. The forecast is in the `"hero"` array.
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


def parse(html: str) -> list[Forecast]:
    blob = _payload(html)
    idx = blob.find('"hero":[')
    if idx < 0:
        raise SourceError("napovedgoriv.si: forecast data ('hero') not found")
    hero, _ = json.JSONDecoder().raw_decode(blob, idx + len('"hero":'))
    target = _date_field(blob, "targetDate", idx)
    as_of = _date_field(blob, "asOf", idx)

    forecasts = []
    for item in hero:
        fuel = _FUELS.get(item.get("fuelType"))
        price = item.get("forecastPrice")
        if fuel is None or price is None:
            continue
        price = round(float(price), 3)
        if not MIN_PRICE <= price <= MAX_PRICE:
            raise SourceError(f"napovedgoriv.si: implausible forecast {price}")
        known, expected = item.get("knownDays") or 0, item.get("expectedDays") or 5
        status = "final" if known >= expected else "first"
        forecasts.append(Forecast("SI", fuel, target, price, status, as_of))
    return forecasts
