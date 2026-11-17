"""Slovenian official (regulated) prices from gov.si."""
from __future__ import annotations

import csv
import io
import re
from datetime import date

from .models import Period, SourceError
from .sanity import check_period, check_timeline

URL = "https://www.gov.si/teme/cene-naftnih-derivatov/element/162094/izvoz.csv"

# "od 17. 11. do 23. 11. 2026" or "od 30. 12. 2025 do 12. 1. 2026"
_DATES = re.compile(
    r"od\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})?\s*do\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"
)


def _period_dates(cell: str) -> tuple[date, date]:
    m = _DATES.search(cell)
    if not m:
        raise SourceError(f"unrecognised date range: {cell!r}")
    d1, m1, y1, d2, m2, y2 = m.groups()
    end = date(int(y2), int(m2), int(d2))
    if y1:
        start_year = int(y1)
    else:
        start_year = end.year - 1 if int(m1) > end.month else end.year
    return date(start_year, int(m1), int(d1)), end


def parse(text: str) -> list[Period]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows or not rows[0] or not rows[0][0].strip().startswith("Datum veljavnosti"):
        raise SourceError("gov.si CSV header not found")
    periods: list[Period] = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        if len(row) < 3:
            raise SourceError(f"short row: {row!r}")
        start, end = _period_dates(row[0])
        for fuel, cell in (("petrol95", row[1]), ("diesel", row[2])):
            p = Period("SI", fuel, start, end, round(float(cell.replace(",", ".")), 3), "gov.si")
            check_period(p)
            periods.append(p)
    if not periods:
        raise SourceError("gov.si CSV has no rows")
    periods.sort(key=lambda p: (p.start, p.fuel))
    check_timeline(periods)
    return periods
