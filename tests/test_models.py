from datetime import date

import pytest

from scraper.models import Forecast, Period, SourceError
from scraper.sanity import check_period, check_timeline


def p(country, fuel, start, end, price=1.5, source="gov.si"):
    return Period(country, fuel, start, end, price, source)


def test_period_json_roundtrip():
    period = p("SI", "petrol95", date(2026, 11, 17), date(2026, 11, 23), 1.444)
    j = period.to_json()
    assert j == {"c": "SI", "f": "petrol95", "from": "2026-11-17", "to": "2026-11-23", "p": 1.444, "s": "gov.si"}
    assert Period.from_json(j) == period


def test_forecast_json_roundtrip():
    f = Forecast("SI", "diesel", date(2026, 11, 24), 1.77, "final", date(2026, 11, 21), 5, 5, -0.01)
    j = f.to_json()
    assert j == {
        "c": "SI", "f": "diesel", "from": "2026-11-24", "p": 1.77, "status": "final", "updated": "2026-11-21",
        "known": 5, "days": 5, "market": -0.01,
    }
    assert Forecast.from_json(j) == f


def test_forecast_from_old_cache():
    old = {"c": "SI", "f": "diesel", "from": "2026-11-24", "p": 1.77, "status": "final", "updated": "2026-11-21"}
    assert Forecast.from_json(old) == Forecast("SI", "diesel", date(2026, 11, 24), 1.77, "final", date(2026, 11, 21))


def test_check_period_rejects_out_of_range():
    d = date(2026, 11, 17)
    for bad in (0.79, 3.51):
        with pytest.raises(SourceError):
            check_period(p("SI", "petrol95", d, d, bad))
    check_period(p("SI", "petrol95", d, d, 1.5))


def test_check_period_rejects_reversed_dates():
    with pytest.raises(SourceError):
        check_period(p("SI", "petrol95", date(2026, 11, 17), date(2026, 11, 16)))


def test_check_timeline_rejects_overlap():
    a = p("SI", "petrol95", date(2026, 11, 10), date(2026, 11, 16))
    with pytest.raises(SourceError):
        check_timeline([a, p("SI", "petrol95", date(2026, 11, 16), date(2026, 11, 23))])
    check_timeline([a, p("SI", "petrol95", date(2026, 11, 17), date(2026, 11, 23))])
    check_timeline([a, p("HR", "petrol95", date(2026, 11, 12), date(2026, 11, 18))])
