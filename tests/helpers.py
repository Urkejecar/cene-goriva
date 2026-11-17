from __future__ import annotations

from datetime import datetime
from io import BytesIO

import openpyxl

HEADER = [
    "Consumer prices of petroleum products inclusive of duties and taxes",
    "CTR",
    "HR_price_with_tax_euro95",
    "HR_price_with_tax_diesel",
    "SI_price_with_tax_euro95",
    "SI_price_with_tax_diesel",
]


def make_eu_xlsx(rows: list[tuple[datetime, float | None, float | None, float | None, float | None]], header=HEADER) -> bytes:
    """A tiny workbook shaped like the EU Weekly Oil Bulletin history file."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Prices with taxes"
    ws.append(header)
    ws.append([None, None, "Euro-super 95  (I)", "Gas oil automobile", "Euro-super 95  (I)", "Gas oil automobile"])
    ws.append(["Date", None, "1000 l", "1000 l", "1000 l", "1000 l"])
    for d, hr95, hrd, si95, sid in rows:
        ws.append([d, "EU_", hr95, hrd, si95, sid])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
