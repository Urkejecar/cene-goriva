import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from scraper import hr_mzoe
from scraper.models import Period, SourceError

GZ = (Path(__file__).parent / "fixtures" / "hr_mzoe_data.gz").read_bytes()


def make_gz(prices: list[float]) -> bytes:
    data = {
        "gorivos": [{"id": 100, "vrsta_goriva_id": 1}],
        "postajas": [{"id": i, "cjenici": [{"gorivo_id": 100, "cijena": c}]} for i, c in enumerate(prices)],
    }
    return gzip.compress(json.dumps(data).encode())


def hr(start, end, price):
    return Period("HR", "petrol95", start, end, price, "mzoe")


def test_regulated_prices_from_real_data():
    assert hr_mzoe.regulated_prices(GZ) == {"petrol95": 1.56, "diesel": 1.82}


def test_rejects_when_no_clear_majority():
    with pytest.raises(SourceError):
        hr_mzoe.regulated_prices(make_gz([1.56, 1.60, 1.70, 13.5, 1.61]))


def test_record_extends_same_price():
    periods = [hr(date(2026, 11, 17), date(2026, 11, 17), 1.56)]
    assert hr_mzoe.record_observation(periods, "petrol95", date(2026, 11, 18), 1.56) == [
        hr(date(2026, 11, 17), date(2026, 11, 18), 1.56)
    ]


def test_record_starts_new_period_on_change():
    periods = [hr(date(2026, 11, 17), date(2026, 11, 23), 1.56)]
    result = hr_mzoe.record_observation(periods, "petrol95", date(2026, 11, 24), 1.50)
    assert result == [periods[0], hr(date(2026, 11, 24), date(2026, 11, 24), 1.50)]


def test_record_same_day_correction():
    # 00:30 run still saw the old price on 11-24; a later run that day sees the new one.
    periods = [hr(date(2026, 11, 17), date(2026, 11, 24), 1.56)]
    result = hr_mzoe.record_observation(periods, "petrol95", date(2026, 11, 24), 1.50)
    assert result == [hr(date(2026, 11, 17), date(2026, 11, 23), 1.56), hr(date(2026, 11, 24), date(2026, 11, 24), 1.50)]
    # and a single-day period is simply corrected
    assert hr_mzoe.record_observation(result, "petrol95", date(2026, 11, 24), 1.51)[-1] == hr(
        date(2026, 11, 24), date(2026, 11, 24), 1.51
    )


def test_record_ignores_older_day():
    periods = [hr(date(2026, 11, 17), date(2026, 11, 18), 1.56)]
    assert hr_mzoe.record_observation(periods, "petrol95", date(2026, 11, 10), 1.40) == periods
