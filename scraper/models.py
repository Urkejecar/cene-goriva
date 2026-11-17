"""Data types shared by all price sources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class SourceError(Exception):
    """A source could not be fetched or parsed, or produced implausible data."""


@dataclass(frozen=True)
class Period:
    """A price valid from `start` to `end` (both inclusive)."""

    country: str  # "SI" | "HR"
    fuel: str  # "petrol95" | "diesel"
    start: date
    end: date
    price: float  # EUR per litre
    source: str  # "gov.si" | "mzoe" | "eu-bulletin"

    def to_json(self) -> dict:
        return {
            "c": self.country,
            "f": self.fuel,
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "p": self.price,
            "s": self.source,
        }

    @staticmethod
    def from_json(d: dict) -> Period:
        return Period(d["c"], d["f"], date.fromisoformat(d["from"]), date.fromisoformat(d["to"]), d["p"], d["s"])


@dataclass(frozen=True)
class Forecast:
    """An expected (unofficial) price for the period starting at `start`."""

    country: str
    fuel: str
    start: date
    price: float
    status: str  # "first" | "final" (napovedgoriv.si) | "estimate" (our HR estimate)
    updated: date
    known: int = 0  # market days the forecast is based on...
    days: int = 5  # ...out of this many
    market: float | None = None  # market price change behind it, EUR/l before VAT

    def to_json(self) -> dict:
        d = {
            "c": self.country,
            "f": self.fuel,
            "from": self.start.isoformat(),
            "p": self.price,
            "status": self.status,
            "updated": self.updated.isoformat(),
            "known": self.known,
            "days": self.days,
        }
        if self.market is not None:
            d["market"] = self.market
        return d

    @staticmethod
    def from_json(d: dict) -> Forecast:
        return Forecast(
            d["c"], d["f"], date.fromisoformat(d["from"]), d["p"], d["status"], date.fromisoformat(d["updated"]),
            d.get("known", 0), d.get("days", 5), d.get("market"),
        )
