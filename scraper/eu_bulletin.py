"""Weekly national average prices from the EU Weekly Oil Bulletin history file."""
from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO

import openpyxl

from .models import Period, SourceError
from .sanity import MAX_PRICE, MIN_PRICE

URL = (
    "https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
    "?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
)
SHEET = "Prices with taxes"
COLUMNS = {
    ("SI", "petrol95"): "SI_price_with_tax_euro95",
    ("SI", "diesel"): "SI_price_with_tax_diesel",
    ("HR", "petrol95"): "HR_price_with_tax_euro95",
    ("HR", "diesel"): "HR_price_with_tax_diesel",
}


def parse(xlsx: bytes) -> list[Period]:
    try:
        wb = openpyxl.load_workbook(BytesIO(xlsx), read_only=True, data_only=True)
    except Exception as e:  # openpyxl raises several unrelated types for bad files
        raise SourceError(f"EU bulletin is not a readable xlsx: {e}") from e
    if SHEET not in wb.sheetnames:
        raise SourceError(f"EU bulletin sheet {SHEET!r} missing")
    rows = wb[SHEET].iter_rows(values_only=True)
    header = list(next(rows, []))
    try:
        index = {key: header.index(name) for key, name in COLUMNS.items()}
    except ValueError as e:
        raise SourceError(f"EU bulletin column missing: {e}") from e

    periods = []
    for row in rows:
        if not row or not isinstance(row[0], datetime):
            continue
        start = row[0].date()
        for (country, fuel), i in index.items():
            value = row[i] if i < len(row) else None
            if not isinstance(value, (int, float)):
                continue
            price = round(value / 1000, 3)  # EUR per 1000 l -> EUR per l
            if not MIN_PRICE <= price <= MAX_PRICE:
                continue  # skip an odd historical cell rather than lose the whole history
            periods.append(Period(country, fuel, start, start + timedelta(days=6), price, "eu-bulletin"))
    wb.close()
    if not periods:
        raise SourceError("EU bulletin has no SI/HR prices")
    periods.sort(key=lambda p: (p.start, p.country, p.fuel))
    return periods
