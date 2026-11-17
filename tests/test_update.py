import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from scraper import check_errors, eu_bulletin, hr_mzoe, napoved, si_gov, update
from tests.helpers import make_eu_xlsx

FIX = Path(__file__).parent / "fixtures"
UTC = timezone.utc
NOW = datetime(2026, 11, 17, 6, 0, tzinfo=UTC)


class FakeWeb:
    def __init__(self):
        self.responses = {
            si_gov.URL: (FIX / "si_gov.csv").read_bytes(),
            napoved.URL: (FIX / "napoved_no_forecast.html").read_bytes(),
            hr_mzoe.URL: (FIX / "hr_mzoe_data.gz").read_bytes(),
            eu_bulletin.URL: make_eu_xlsx([
                (datetime(2021, 11, 15), 1480.94, 1470.56, 1371.51, 1473.6),
                (datetime(2026, 11, 9), 1748.83, 2024.63, 1634.36, 1950.29),
            ]),
        }
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses[url]


def run(tmp_path, web, now=NOW):
    return update.run(now, web, tmp_path / "data", tmp_path / "site" / "data.json")


def test_full_run(tmp_path):
    data = run(tmp_path, FakeWeb())
    assert data["errors"] == []
    assert sum(1 for p in data["periods"] if p["s"] == "gov.si") == 266
    assert {"c": "HR", "f": "petrol95", "from": "2026-11-17", "to": "2026-11-17", "p": 1.56, "s": "mzoe"} in data["periods"]
    assert {"c": "HR", "f": "diesel", "from": "2026-11-17", "to": "2026-11-17", "p": 1.82, "s": "mzoe"} in data["periods"]
    assert json.loads((tmp_path / "site" / "data.json").read_text(encoding="utf-8")) == data
    for name in ("si_gov", "hr_mzoe", "eu_bulletin", "napoved"):
        assert (tmp_path / "data" / f"{name}.json").exists()


def test_failing_source_keeps_cache(tmp_path):
    web = FakeWeb()
    run(tmp_path, web)
    cache = (tmp_path / "data" / "si_gov.json").read_bytes()
    web.responses[si_gov.URL] = b"<html>500</html>"
    data = run(tmp_path, web, NOW + timedelta(minutes=30))
    assert [e["source"] for e in data["errors"]] == ["si_gov"]
    assert sum(1 for p in data["periods"] if p["s"] == "gov.si") == 266
    assert (tmp_path / "data" / "si_gov.json").read_bytes() == cache


def test_napoved_throttled(tmp_path):
    # Schedule runs at :00 and :30; napoved only on the :00 run, EU once a day.
    web = FakeWeb()
    run(tmp_path, web)  # 06:00 UTC
    run(tmp_path, web, NOW + timedelta(minutes=35))  # 06:35 UTC
    assert web.calls.count(napoved.URL) == 1
    assert web.calls.count(eu_bulletin.URL) == 1
    assert web.calls.count(si_gov.URL) == 2
    run(tmp_path, web, NOW + timedelta(minutes=62))  # 07:02 UTC
    assert web.calls.count(napoved.URL) == 2
    assert web.calls.count(eu_bulletin.URL) == 1


def test_unchanged_run_does_not_rewrite_caches(tmp_path):
    web = FakeWeb()
    run(tmp_path, web)
    before = {f.name: f.read_bytes() for f in (tmp_path / "data").iterdir()}
    run(tmp_path, web, NOW + timedelta(minutes=62))
    after = {f.name: f.read_bytes() for f in (tmp_path / "data").iterdir()}
    assert after == before


def test_today_is_ljubljana_date():
    assert update.today_in_ljubljana(datetime(2026, 11, 16, 23, 30, tzinfo=UTC)) == date(2026, 11, 17)


def test_check_errors_exit_code(tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"errors": [{"source": "si_gov", "message": "boom"}]}), encoding="utf-8")
    assert check_errors.main([str(f)]) == 1
    f.write_text(json.dumps({"errors": []}), encoding="utf-8")
    assert check_errors.main([str(f)]) == 0
