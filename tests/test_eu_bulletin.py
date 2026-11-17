from datetime import date, datetime

import pytest

from scraper import eu_bulletin
from scraper.models import Period, SourceError
from tests.helpers import HEADER, make_eu_xlsx


def test_parses_weekly_rows():
    xlsx = make_eu_xlsx([
        (datetime(2026, 11, 9), 1748.83, 2024.63, 1634.36, 1950.29),
        (datetime(2021, 11, 15), 1480.94, 1470.56, 1371.51, 1473.6),
    ])
    periods = eu_bulletin.parse(xlsx)
    assert len(periods) == 8
    assert Period("HR", "petrol95", date(2021, 11, 15), date(2021, 11, 21), 1.481, "eu-bulletin") in periods
    si_diesel = [p for p in periods if p.country == "SI" and p.fuel == "diesel" and p.start == date(2026, 11, 9)]
    assert [p.price for p in si_diesel] == [1.95]
    assert periods == sorted(periods, key=lambda p: p.start)


def test_skips_empty_cells():
    periods = eu_bulletin.parse(make_eu_xlsx([(datetime(2010, 11, 29), None, None, 1229, 1192)]))
    assert {p.country for p in periods} == {"SI"}


def test_missing_column_raises():
    header = HEADER[:-1] + ["something_else"]
    with pytest.raises(SourceError):
        eu_bulletin.parse(make_eu_xlsx([(datetime(2026, 11, 9), 1, 2, 3, 4)], header=header))
