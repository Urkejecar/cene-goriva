from datetime import date
from pathlib import Path

import pytest

from scraper import napoved
from scraper.models import Forecast, SourceError

FIX = Path(__file__).parent / "fixtures"
HTML = (FIX / "napoved_no_forecast.html").read_bytes().decode("utf-8")
# Tuesday, one market day known: the headline forecast is still empty, the early one is not.
ONE_DAY = (FIX / "napoved_one_day.html").read_bytes().decode("utf-8")


def with_petrol_forecast(price: float, known_days: int) -> str:
    html = HTML.replace(
        r'\"previousPrice\":1.506,\"forecastPrice\":null',
        r'\"previousPrice\":1.506,\"forecastPrice\":' + str(price),
        1,
    )
    html = html.replace(r'\"knownDays\":0', r'\"knownDays\":' + str(known_days), 1)
    assert html != HTML
    return html


def test_no_forecast_yet():
    assert napoved.parse(HTML) == []


def test_first_forecast():
    assert napoved.parse(with_petrol_forecast(1.412, 3)) == [
        Forecast("SI", "petrol95", date(2026, 11, 24), 1.412, "first", date(2026, 11, 17), 3, 5)
    ]


def test_early_forecast_from_first_known_day():
    assert napoved.parse(ONE_DAY) == [
        Forecast("SI", "petrol95", date(2026, 11, 24), 1.429, "first", date(2026, 11, 17), 1, 5, -0.012398),
        Forecast("SI", "diesel", date(2026, 11, 24), 1.791, "first", date(2026, 11, 17), 1, 5, -0.005587),
    ]


def test_final_forecast():
    [f] = napoved.parse(with_petrol_forecast(1.412, 5))
    assert f.status == "final"


def test_missing_hero_raises():
    with pytest.raises(SourceError):
        napoved.parse("<html></html>")
