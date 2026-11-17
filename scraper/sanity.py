"""Plausibility checks so a half-broken parse never publishes wrong numbers."""
from __future__ import annotations

from itertools import groupby

from .models import Period, SourceError

MIN_PRICE = 0.80
MAX_PRICE = 3.50


def check_period(p: Period) -> None:
    if not MIN_PRICE <= p.price <= MAX_PRICE:
        raise SourceError(f"implausible price {p.price} for {p.country} {p.fuel} from {p.start}")
    if p.end < p.start:
        raise SourceError(f"period ends before it starts: {p.start}..{p.end}")


def check_timeline(periods: list[Period]) -> None:
    key = lambda p: (p.country, p.fuel)  # noqa: E731
    for _, group in groupby(sorted(periods, key=lambda p: (key(p), p.start)), key=key):
        previous = None
        for p in group:
            if previous is not None and p.start <= previous.end:
                raise SourceError(f"overlapping periods {previous.start}..{previous.end} and {p.start}..{p.end}")
            previous = p
