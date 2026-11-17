from datetime import date
from pathlib import Path

import pytest

from scraper import napoved
from scraper.models import Forecast, SourceError

HTML = (Path(__file__).parent / "fixtures" / "napoved_no_forecast.html").read_bytes().decode("utf-8")


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
        Forecast("SI", "petrol95", date(2026, 11, 24), 1.412, "first", date(2026, 11, 17))
    ]


def test_final_forecast():
    [f] = napoved.parse(with_petrol_forecast(1.412, 5))
    assert f.status == "final"


def test_missing_hero_raises():
    with pytest.raises(SourceError):
        napoved.parse("<html></html>")
