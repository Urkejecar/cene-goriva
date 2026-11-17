from datetime import date
from pathlib import Path

import pytest

from scraper import si_gov
from scraper.models import Period, SourceError

FIXTURE = (Path(__file__).parent / "fixtures" / "si_gov.csv").read_bytes().decode("utf-8")


def series(fuel):
    return [p for p in si_gov.parse(FIXTURE) if p.fuel == fuel]


def test_parses_all_rows():
    assert len(si_gov.parse(FIXTURE)) == 266


def test_latest_row():
    assert series("petrol95")[-1] == Period("SI", "petrol95", date(2026, 11, 17), date(2026, 11, 23), 1.444, "gov.si")
    assert series("diesel")[-1].price == 1.798


def test_earliest_row():
    first = series("petrol95")[0]
    assert (first.start, first.end, first.price) == (date(2022, 6, 21), date(2022, 7, 4), 1.755)


def test_year_crossing_without_start_year():
    p = next(p for p in series("petrol95") if p.end == date(2023, 1, 3))
    assert p.start == date(2022, 12, 20)
    assert p.price == 1.242


def test_year_crossing_with_start_year():
    p = next(p for p in series("petrol95") if p.end == date(2026, 1, 12))
    assert p.start == date(2025, 12, 30)


def test_garbage_raises():
    with pytest.raises(SourceError):
        si_gov.parse("<html>Napaka</html>")
