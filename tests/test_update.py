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


def test_check_errors_fails_only_on_alerts(tmp_path):
    f = tmp_path / "data.json"
    boom = [{"source": "si_gov", "message": "boom"}]
    f.write_text(json.dumps({"errors": boom, "alerts": ["si_gov"]}), encoding="utf-8")
    assert check_errors.main([str(f)]) == 1
    f.write_text(json.dumps({"errors": boom, "alerts": []}), encoding="utf-8")
    assert check_errors.main([str(f)]) == 0


def failing_runs(tmp_path, web, hours):
    """Run at NOW (all OK), then with gov.si broken at NOW + each of `hours`; return each run's alerts."""
    run(tmp_path, web)
    web.responses[si_gov.URL] = b"<html>500</html>"
    return [run(tmp_path, web, NOW + timedelta(hours=h))["alerts"] for h in hours]


def test_single_failure_does_not_alert(tmp_path):
    assert failing_runs(tmp_path, FakeWeb(), [0.5]) == [[]]


def test_alert_after_three_hours_then_once_a_day(tmp_path):
    alerts = failing_runs(tmp_path, FakeWeb(), [0.5, 1, 3.4, 3.6, 4, 12, 27.6])
    assert alerts == [[], [], [], ["si_gov"], [], [], ["si_gov"]]


def test_recovery_clears_failure(tmp_path):
    web = FakeWeb()
    failing_runs(tmp_path, web, [0.5, 1])
    web.responses[si_gov.URL] = (FIX / "si_gov.csv").read_bytes()
    run(tmp_path, web, NOW + timedelta(hours=2))
    web.responses[si_gov.URL] = b"<html>500</html>"
    # failing again from 2.5 h: no alert at 4 h (only 1.5 h of failure)
    assert run(tmp_path, web, NOW + timedelta(hours=2.5))["alerts"] == []
    assert run(tmp_path, web, NOW + timedelta(hours=4))["alerts"] == []
