from datetime import date, datetime, timezone

from scraper import build
from scraper.models import Forecast, Period


def per(country, start, end, price, source, fuel="petrol95"):
    return Period(country, fuel, start, end, price, source)


def test_combine_uses_eu_only_before_official():
    eu = [
        per("SI", date(2022, 6, 13), date(2022, 6, 19), 1.70, "eu-bulletin"),
        per("SI", date(2022, 6, 20), date(2022, 6, 26), 1.80, "eu-bulletin"),
        per("SI", date(2022, 6, 27), date(2022, 7, 3), 1.81, "eu-bulletin"),
    ]
    official = [per("SI", date(2022, 6, 21), date(2022, 7, 4), 1.755, "gov.si")]
    assert build.combine(official, eu) == [
        eu[0],
        per("SI", date(2022, 6, 20), date(2022, 6, 20), 1.80, "eu-bulletin"),
        official[0],
    ]


def test_combine_fills_gap_before_official():
    # HR: last EU week ends 11-15, our own records start 11-17 -> EU fills 11-16 (no slanted line).
    eu = [per("HR", date(2026, 11, 9), date(2026, 11, 15), 1.749, "eu-bulletin")]
    official = [per("HR", date(2026, 11, 17), date(2026, 11, 17), 1.56, "mzoe")]
    assert build.combine(official, eu)[0] == per("HR", date(2026, 11, 9), date(2026, 11, 16), 1.749, "eu-bulletin")


def test_combine_eu_only_series():
    eu = [per("HR", date(2026, 11, 9), date(2026, 11, 15), 1.749, "eu-bulletin")]
    official = [per("SI", date(2026, 11, 17), date(2026, 11, 23), 1.444, "gov.si")]
    assert build.combine(official, eu) == [eu[0], official[0]]


def test_site_data_drops_old_and_past_forecasts():
    today = date(2026, 11, 17)
    old = per("SI", date(2020, 1, 6), date(2020, 1, 12), 1.2, "eu-bulletin")
    recent = per("SI", date(2021, 11, 15), date(2021, 11, 21), 1.37, "eu-bulletin")
    past_fc = Forecast("SI", "petrol95", date(2026, 11, 17), 1.44, "final", date(2026, 11, 14))
    next_fc = Forecast("SI", "petrol95", date(2026, 11, 24), 1.41, "first", date(2026, 11, 19))
    checked = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)
    data = build.site_data([old, recent], [past_fc, next_fc], [], checked, today)
    assert data == {
        "checked_at": "2026-11-17T06:00:00Z",
        "today": "2026-11-17",
        "periods": [recent.to_json()],
        "forecasts": [next_fc.to_json()],
        "errors": [],
    }
